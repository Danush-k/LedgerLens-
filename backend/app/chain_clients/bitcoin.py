import requests

from app.chain_clients.base import Chain, ChainClient, Transfer
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

    def get_outgoing_transfers(self, address: str, limit: int = 50) -> list[Transfer]:
        base_url = get_settings().bitcoin_api_base_url
        response = self._session.get(f"{base_url}/address/{address}/txs", timeout=15)
        response.raise_for_status()
        txs = response.json()

        transfers: list[Transfer] = []
        for tx in txs:
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
