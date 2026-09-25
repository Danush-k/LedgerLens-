import threading
import time

import requests

from app.chain_clients.base import Chain, ChainClient, Transfer
from app.chain_clients.http import get_with_retry
from app.config import get_settings

_SATOSHIS_PER_BTC = 100_000_000

# Above this many inputs a transaction is a service consolidating deposits,
# not one person spending from their own wallets. The threshold is generous:
# a personal wallet rarely spends more than a handful of UTXOs at once, while
# exchange sweeps run to hundreds or thousands.
MAX_COSPEND_INPUTS = 50


# Bitcoin data providers, in preference order.
#
# Every one of these is free and shared, so any of them can refuse at any
# time - and being refused by one says nothing about the others. Keeping
# several, behind a common shape, is what turns "the provider is busy" from
# a failed trace into a slightly slower one. They do not share an API, so
# each has a reader that normalises its response into the Esplora shape the
# rest of this client already speaks.


# Esplora's first page is the most recent 25 transactions only - for an
# address anyone can send dust to (and people do, for years, to famous
# addresses), the transaction that actually moved real money can sit well
# outside that page. Without paging past it, "no outgoing transfers found"
# stops meaning "this wallet is clean" and starts meaning "this wallet
# hasn't been touched *recently*" - a materially different, and wrong,
# claim. Capped rather than unbounded: an address with an unusually long
# history should cost a few extra requests, not become an unpaged fetch
# that never returns.
_ESPLORA_MAX_PAGES = 4


def _read_esplora(session: requests.Session, base_url: str, address: str) -> list[dict]:
    """Blockstream and other Esplora hosts, which need no translation.

    Paging costs more requests than a single fetch, and every extra request
    is one more chance for a free, shared API to refuse. A later page
    failing after its own retries is not license to discard the pages that
    already succeeded - this address's most recent, most relevant history
    is real data, and losing it because page 6 of 12 timed out would trade
    the pagination bug for a reliability one. Only the *first* page failing
    is a genuine "could not reach this address at all", and is left to
    propagate as one.
    """
    all_txs: list[dict] = []
    last_txid: str | None = None
    for page_num in range(_ESPLORA_MAX_PAGES):
        url = (f"{base_url}/address/{address}/txs" if last_txid is None
              else f"{base_url}/address/{address}/txs/chain/{last_txid}")
        try:
            page = get_with_retry(session, url, attempts=4).json()
        except Exception:
            if page_num == 0:
                raise
            break  # keep what earlier pages already found
        if not page:
            break
        all_txs.extend(page)
        last_txid = page[-1].get("txid")
        # A page shorter than Esplora's own page size (25) is the last one -
        # asking again would just re-request the same tail.
        if len(page) < 25 or not last_txid:
            break
    return all_txs


_BLOCKCHAIN_INFO_PAGE = 50
_BLOCKCHAIN_INFO_MAX_PAGES = 6  # same reasoning as Esplora's page cap, above


def _read_blockchain_info(session: requests.Session, base_url: str,
                           address: str) -> list[dict]:
    """blockchain.info's rawaddr, mapped onto the Esplora shape.

    Values are already in satoshis in both, so only the field names and the
    nesting differ. Paged the same way and for the same reason as Esplora:
    the first page is only the most recent transactions.
    """
    raw_txs: list[dict] = []
    for page in range(_BLOCKCHAIN_INFO_MAX_PAGES):
        try:
            response = get_with_retry(
                session, f"{base_url}/rawaddr/{address}",
                params={"limit": _BLOCKCHAIN_INFO_PAGE, "offset": page * _BLOCKCHAIN_INFO_PAGE},
                attempts=4)
            batch = response.json().get("txs", [])
        except Exception:
            if page == 0:
                raise
            break  # a later page failing must not discard the ones already fetched
        if not batch:
            break
        raw_txs.extend(batch)
        if len(batch) < _BLOCKCHAIN_INFO_PAGE:
            break

    normalised: list[dict] = []
    for tx in raw_txs:
        normalised.append({
            "txid": tx.get("hash", ""),
            "status": {"block_time": int(tx.get("time", 0))},
            "vin": [
                {"prevout": {
                    "scriptpubkey_address": (vin.get("prev_out") or {}).get("addr"),
                    "value": (vin.get("prev_out") or {}).get("value", 0),
                }}
                for vin in tx.get("inputs", [])
            ],
            "vout": [
                {"scriptpubkey_address": out.get("addr"), "value": out.get("value", 0)}
                for out in tx.get("out", [])
            ],
        })
    return normalised


_PROVIDERS = [
    ("mempool.space", "https://mempool.space/api", _read_esplora),
    ("blockstream.info", "https://blockstream.info/api", _read_esplora),
    ("blockchain.info", "https://blockchain.info", _read_blockchain_info),
]


def _providers() -> list[tuple[str, str, object]]:
    """The configured host first, then the public fallbacks behind it.

    A deployment pointing at its own Esplora node should have it tried
    first, but it replaces nothing - the fallbacks are the whole point.
    """
    configured = (get_settings().bitcoin_api_base_url or "").rstrip("/")
    providers = list(_PROVIDERS)
    if configured:
        known = {url for _, url, _ in providers}
        if configured not in known:
            providers.insert(0, (_host_label(configured), configured, _read_esplora))
        else:
            providers.sort(key=lambda p: p[1] != configured)
    return providers


def _host_label(url: str) -> str:
    return url.split("://", 1)[-1].split("/", 1)[0]


# A provider that just refused will almost certainly refuse the next address
# too - throttling is applied to the caller, not the query. Benching it
# process-wide means one address pays the timeout instead of every address
# paying it, which is the difference between a trace that is slightly slower
# under throttling and one that crawls.
_benched: dict[str, float] = {}
_bench_lock = threading.Lock()
BENCH_SECONDS = 120.0


def _bench(label: str) -> None:
    with _bench_lock:
        _benched[label] = time.monotonic() + BENCH_SECONDS


def _is_benched(label: str) -> bool:
    with _bench_lock:
        return _benched.get(label, 0.0) > time.monotonic()


class BitcoinClient(ChainClient):
    """Reads outgoing transfers for a Bitcoin address via Blockstream's
    public Esplora API. Bitcoin uses the UTXO model, not the account model
    EVM chains use, so "outgoing transfer" means: this address was spent as
    an input on a transaction, and funds landed on some other output address.

    No API key needed at all - this endpoint is fully public.
    """

    chain = Chain.BITCOIN

    def __init__(self, session: requests.Session | None = None):
        self._session = session or requests.Session()
        self._tx_cache: dict[str, list[dict]] = {}
        self._providers = _providers()
        self._preferred = 0

    def _get_txs(self, address: str) -> list[dict]:
        """This address's transactions, from whichever provider answers.

        A provider refusing is a reason to ask elsewhere, not to give up.
        Only when every one of them refuses is this genuinely a data
        availability problem - and the error then names each so the failure
        can be told apart from a wallet that has no history.
        """
        if address in self._tx_cache:
            return self._tx_cache[address]

        providers = self._providers
        # Round-robin the starting provider on every address, rather than
        # sticking to whichever one last answered. Each provider is paced
        # by its own independent per-host limiter (http.py), so pinning
        # every address in a wide hop to a single provider caps the whole
        # hop at *that one provider's* rate limit even while a second,
        # equally healthy provider sits idle - which is exactly what turned
        # a 276-address hop into a multi-minute stall with only one of
        # three providers (blockchain.info) actually down. Spreading
        # addresses across every currently-healthy provider uses all of
        # their budgets at once instead of just one.
        start = self._preferred
        self._preferred = (self._preferred + 1) % len(providers)
        order = providers[start:] + providers[:start]
        # Providers known to be refusing go last rather than being dropped:
        # if every one is benched we still have to ask somebody.
        order.sort(key=lambda p: _is_benched(p[0]))

        if all(_is_benched(label) for label, _, _ in order):
            # Every provider already failed within the bench window for
            # some other address in this same trace. Retrying all of them
            # again here pays the same timeouts a second time for no new
            # information - failing immediately lets the hop finish (as
            # "could not look", honestly) instead of grinding through the
            # same dead ends address by address until the trace's own
            # timeout cuts it off.
            raise RuntimeError(
                "every Bitcoin data provider is currently rate-limited or "
                "unreachable (" + ", ".join(label for label, _, _ in order) + ")")

        errors: list[str] = []
        for label, base_url, read in order:
            try:
                txs = read(self._session, base_url, address)
                self._tx_cache[address] = txs
                return txs
            except Exception as exc:  # noqa: BLE001 - try the next provider
                _bench(label)
                errors.append(f"{label}: {type(exc).__name__}")

        raise RuntimeError(
            "no Bitcoin data provider could be reached (" + "; ".join(errors) + ")")

    def get_outgoing_transfers(self, address: str, limit: int = 50) -> list[Transfer]:
        transfers: list[Transfer] = []
        for tx in self._get_txs(address):
            spent_as_input = any(
                (vin.get("prevout") or {}).get("scriptpubkey_address") == address
                for vin in tx.get("vin", [])
            )
            if not spent_as_input:
                continue  # this address only received funds in this tx

            status = tx.get("status", {})
            timestamp = int(status.get("block_time", 0))
            tx_hash = tx.get("txid", "")

            for vout in tx.get("vout", []):
                to_addr = vout.get("scriptpubkey_address")
                if not to_addr or to_addr == address:
                    continue  # skip change outputs back to the same address
                value = vout.get("value", 0) / _SATOSHIS_PER_BTC
                if value <= 0:
                    continue
                transfers.append(
                    Transfer(
                        tx_hash=tx_hash,
                        chain=self.chain,
                        from_address=address,
                        to_address=to_addr,
                        value=value,
                        timestamp=timestamp,
                    )
                )
            if len(transfers) >= limit:
                break
        return transfers[:limit]

    def get_co_spent_addresses(self, address: str) -> set[str]:
        """The common-input-ownership heuristic: if `address` was spent as
        one of several inputs on the same transaction, every other input
        address on that transaction was necessarily signed by whoever
        controls `address` too - a wallet can't spend a UTXO it doesn't
        hold the key for. That's a strong same-owner signal, not a guess.
        Reuses the same tx list `get_outgoing_transfers` already fetched.

        Consolidation sweeps are excluded. An exchange periodically gathers
        thousands of customer deposit addresses into one transaction, and
        while the heuristic is still technically true there - the exchange
        does hold all those keys - the "owner" it identifies is the exchange,
        not a suspect. Merging on those transactions chains unrelated
        customers into one entity of several thousand addresses, which is
        how this heuristic produces a criminal organisation out of an
        exchange's cold-storage routine.
        """
        co_spent: set[str] = set()
        for tx in self._get_txs(address):
            input_addrs = {
                (vin.get("prevout") or {}).get("scriptpubkey_address")
                for vin in tx.get("vin", [])
            }
            input_addrs.discard(None)
            if len(input_addrs) > MAX_COSPEND_INPUTS:
                continue  # consolidation sweep, not a personal wallet set
            if address in input_addrs and len(input_addrs) > 1:
                co_spent |= input_addrs - {address}
        return co_spent
