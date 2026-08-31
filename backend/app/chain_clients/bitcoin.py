import requests

from app.chain_clients.base import Chain, ChainClient, Transfer
from app.chain_clients.http import get_with_retry
from app.config import get_settings

_SATOSHIS_PER_BTC = 100_000_000


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

    def _get_txs(self, address: str) -> list[dict]:
        if address not in self._tx_cache:
            base_url = get_settings().bitcoin_api_base_url
            response = get_with_retry(self._session, f"{base_url}/address/{address}/txs")
            self._tx_cache[address] = response.json()
        return self._tx_cache[address]

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
        """
        co_spent: set[str] = set()
        for tx in self._get_txs(address):
            input_addrs = {
                (vin.get("prevout") or {}).get("scriptpubkey_address")
                for vin in tx.get("vin", [])
            }
            input_addrs.discard(None)
            if address in input_addrs and len(input_addrs) > 1:
                co_spent |= input_addrs - {address}
        return co_spent
