"""Tron client, focused on TRC-20 USDT.

Tron matters more than its market share suggests. USDT on Tron is the rail
most Indian crypto fraud actually settles on: transfers are near-free, the
asset is dollar-stable so a scammer is not exposed to price swings between
collection and cash-out, and every major exchange serving Indian users
accepts TRC-20 deposits. A tool built for this problem statement that
cannot follow USDT-TRC20 is missing the dominant case.

Only USDT is traced. Tron addresses hold many tokens, and a transfer list
mixing USDT, TRX and arbitrary TRC-20 tokens cannot be summed - "0.5" of
one is not comparable to "0.5" of another, so fan-out totals, taint ratios
and the value columns in the report would all be meaningless. Restricting
to the single asset the fraud uses keeps every downstream number coherent.
Native TRX is deliberately excluded for the same reason: in these cases it
is the gas, not the proceeds.
"""
import requests

from app.chain_clients.base import Chain, ChainClient, Transfer
from app.chain_clients.http import get_with_retry

TRONGRID_BASE = "https://api.trongrid.io"

# Tether's TRC-20 contract on Tron. Fixed, and worth pinning rather than
# discovering: a fake token can claim the symbol "USDT", so matching on the
# contract address is the only reliable identification.
USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
USDT_DECIMALS = 6

MAX_TRANSFERS = 200


class TronClient(ChainClient):
    """Reads outgoing TRC-20 USDT transfers for a Tron address.

    Read-only GET requests against a public API. No wallet, no private key,
    no funds are involved anywhere in this class.
    """

    chain = Chain.TRON

    def __init__(self, session: requests.Session | None = None):
        self._session = session or requests.Session()
        self._cache: dict[str, list[dict]] = {}

    def _fetch_trc20(self, address: str) -> list[dict]:
        """All TRC-20 events touching this address, newest first.

        TronGrid returns transfers in both directions; filtering to outgoing
        happens in the caller so the same fetch can serve other uses later.
        """
        if address in self._cache:
            return self._cache[address]
        response = get_with_retry(
            self._session,
            f"{TRONGRID_BASE}/v1/accounts/{address}/transactions/trc20",
            params={"limit": MAX_TRANSFERS, "only_confirmed": "true"},
            timeout=8,
        )
        payload = response.json()
        # TronGrid answers 200 with success=false for a malformed address
        # rather than an HTTP error, so the body has to be checked too.
        if isinstance(payload, dict) and payload.get("success") is False:
            raise ValueError(f"TronGrid rejected {address}: {payload.get('error', 'unknown')}")
        data = payload.get("data", []) if isinstance(payload, dict) else []
        self._cache[address] = data
        return data

    def get_outgoing_transfers(self, address: str) -> list[Transfer]:
        transfers: list[Transfer] = []
        for event in self._fetch_trc20(address):
            token = event.get("token_info") or {}
            if token.get("address") != USDT_CONTRACT:
                continue  # a different TRC-20 token, or a lookalike
            if event.get("from") != address:
                continue  # incoming, not outgoing
            to_address = event.get("to")
            raw_value = event.get("value")
            if not to_address or raw_value is None:
                continue
            try:
                # TronGrid returns the amount as a string of base units.
                value = int(raw_value) / (10 ** int(token.get("decimals", USDT_DECIMALS)))
            except (TypeError, ValueError):
                continue
            transfers.append(Transfer(
                tx_hash=event.get("transaction_id", ""),
                chain=Chain.TRON,
                from_address=address,
                to_address=to_address,
                value=value,
                # block_timestamp is milliseconds on TronGrid, unlike the
                # second-based timestamps every other client here returns.
                timestamp=int(event.get("block_timestamp", 0)) // 1000,
                asset="USDT",
            ))
        return transfers
