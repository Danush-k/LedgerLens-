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


def _read_esplora(session: requests.Session, base_url: str, address: str) -> list[dict]:
    """Blockstream and other Esplora hosts, which need no translation."""
    response = get_with_retry(session, f"{base_url}/address/{address}/txs", attempts=2)
    return response.json()


def _read_blockchain_info(session: requests.Session, base_url: str,
                           address: str) -> list[dict]:
    """blockchain.info's rawaddr, mapped onto the Esplora shape.

    Values are already in satoshis in both, so only the field names and the
    nesting differ.
    """
    response = get_with_retry(
        session, f"{base_url}/rawaddr/{address}",
        params={"limit": 50}, attempts=2)
    payload = response.json()

    normalised: list[dict] = []
    for tx in payload.get("txs", []):
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
    ("blockstream.info", "https://blockstream.info/api", _read_esplora),
    ("blockchain.info", "https://blockchain.info", _read_blockchain_info),
    ("mempool.space", "https://mempool.space/api", _read_esplora),
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
        order = providers[self._preferred:] + providers[:self._preferred]
        # Providers known to be refusing go last rather than being dropped:
        # if every one is benched we still have to ask somebody.
        order.sort(key=lambda p: _is_benched(p[0]))
        errors: list[str] = []

        for offset, (label, base_url, read) in enumerate(order):
            try:
                txs = read(self._session, base_url, address)
                self._tx_cache[address] = txs
                # Stay on whichever answered: a provider throttling us tends
                # to keep throttling us, and starting each fetch back at the
                # failing one pays its timeout every single time.
                self._preferred = (self._preferred + offset) % len(providers)
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
