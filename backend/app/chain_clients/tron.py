import logging
from app.chain_clients.base import Chain, ChainClient, Transfer
from app.chain_clients.http import get

logger = logging.getLogger(__name__)

TRON_GRID_API = "https://api.trongrid.io/v1/accounts"
TRC20_USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"


class TronClient(ChainClient):
    """Tron client for TRC-20 USDT token transfers and TRX native gas transfers
    using the TronGrid REST API.
    """

    chain = Chain.TRON

    def get_outgoing_transfers(self, address: str) -> list[Transfer]:
        transfers: list[Transfer] = []
        
        # 1. Fetch TRC-20 USDT token transfers
        try:
            url = f"{TRON_GRID_API}/{address}/transactions/trc20"
            params = {
                "contract_address": TRC20_USDT_CONTRACT,
                "limit": 50,
                "only_from": "true",
            }
            data = get(url, params=params)
            rows = data.get("data") or []
            
            for row in rows:
                if row.get("from") == address:
                    val_raw = float(row.get("value", 0))
                    decimals = int(row.get("token_info", {}).get("decimals", 6))
                    value = val_raw / (10 ** decimals)
                    
                    transfers.append(
                        Transfer(
                            tx_hash=row.get("transaction_id", ""),
                            chain=Chain.TRON,
                            from_address=row.get("from", ""),
                            to_address=row.get("to", ""),
                            value=round(value, 4),
                            timestamp=int(row.get("block_timestamp", 0)) // 1000,
                        )
                    )
        except Exception as err:
            logger.warning(f"[TronClient] Error fetching TRC20 transfers for {address}: {err}")

        # 2. Fallback / supplementary: Fetch native TRX transactions if TRC-20 returned few/no records
        if len(transfers) < 5:
            try:
                url = f"{TRON_GRID_API}/{address}/transactions"
                params = {"limit": 30, "only_from": "true"}
                data = get(url, params=params)
                rows = data.get("data") or []

                for row in rows:
                    raw_data = row.get("raw_data") or {}
                    contracts = raw_data.get("contract") or []
                    for contract in contracts:
                        val_dict = contract.get("parameter", {}).get("value", {})
                        if val_dict.get("owner_address") == address and val_dict.get("to_address"):
                            amount_sun = val_dict.get("amount", 0)
                            transfers.append(
                                Transfer(
                                    tx_hash=row.get("txID", ""),
                                    chain=Chain.TRON,
                                    from_address=address,
                                    to_address=val_dict.get("to_address", ""),
                                    value=round(amount_sun / 1_000_000, 4),
                                    timestamp=int(raw_data.get("timestamp", 0)) // 1000,
                                )
                            )
            except Exception as err:
                logger.warning(f"[TronClient] Error fetching native TRX transfers for {address}: {err}")

        return transfers

    def get_inflow_transfers(self, address: str) -> list[Transfer]:
        """Fetch incoming transfers to trace backward gas funding (Seed Funder)."""
        inflows: list[Transfer] = []
        try:
            url = f"{TRON_GRID_API}/{address}/transactions/trc20"
            params = {"limit": 20, "only_to": "true"}
            data = get(url, params=params)
            rows = data.get("data") or []
            
            for row in rows:
                if row.get("to") == address:
                    val_raw = float(row.get("value", 0))
                    decimals = int(row.get("token_info", {}).get("decimals", 6))
                    value = val_raw / (10 ** decimals)
                    inflows.append(
                        Transfer(
                            tx_hash=row.get("transaction_id", ""),
                            chain=Chain.TRON,
                            from_address=row.get("from", ""),
                            to_address=address,
                            value=round(value, 4),
                            timestamp=int(row.get("block_timestamp", 0)) // 1000,
                        )
                    )
        except Exception as err:
            logger.warning(f"[TronClient] Error fetching inflow transfers for {address}: {err}")

        return inflows
