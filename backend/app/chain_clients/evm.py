import requests

from app.chain_clients.base import Chain, ChainClient, Transfer
from app.chain_clients.http import get_with_retry
from app.chain_clients.keypool import pool_from_setting
from app.config import get_settings

# Etherscan, BscScan and PolygonScan all run the same explorer API shape
# (module=account&action=txlist). One client, three chains.
_EXPLORER_CONFIG = {
    Chain.ETHEREUM: {
        "base_url": "https://api.etherscan.io/api",
        "api_key_attr": "etherscan_api_key",
        "native_unit_decimals": 18,
    },
    Chain.BSC: {
        "base_url": "https://api.bscscan.com/api",
        "api_key_attr": "bscscan_api_key",
        "native_unit_decimals": 18,
    },
    Chain.POLYGON: {
        "base_url": "https://api.polygonscan.com/api",
        "api_key_attr": "polygonscan_api_key",
        "native_unit_decimals": 18,
    },
}


def _is_rate_limited(payload: dict) -> bool:
    """Etherscan-family throttling, which arrives as a 200 rather than a 429."""
    if not isinstance(payload, dict) or payload.get("status") not in ("0", 0):
        return False
    text = f"{payload.get('message', '')} {payload.get('result', '')}".lower()
    return "rate limit" in text or "max calls" in text or "too many" in text


class EVMClient(ChainClient):
    """Reads outgoing native-currency transfers for an address on any EVM
    chain backed by an Etherscan-family explorer API.

    This only ever performs read-only GET requests against a public API.
    No wallet, private key, or funds are involved anywhere in this class.
    """

    def __init__(self, chain: Chain, session: requests.Session | None = None):
        if chain not in _EXPLORER_CONFIG:
            raise ValueError(f"{chain.value} is not an EVM chain handled by this client")
        self.chain = chain
        self._config = _EXPLORER_CONFIG[chain]
        self._session = session or requests.Session()
        # One pool per client instance. Built here rather than per request so
        # the rotation position and the benched-key state survive across the
        # many calls a single trace makes.
        self._keys = pool_from_setting(
            getattr(get_settings(), self._config["api_key_attr"])
        )

    def get_outgoing_transfers(self, address: str, limit: int = 50) -> list[Transfer]:
        api_key = self._keys.get()
        decimals = self._config["native_unit_decimals"]
        transfers: list[Transfer] = []
        seen_tx_hashes = set()

        # 1. Native currency transfers (ETH / BNB / MATIC)
        try:
            params_native = {
                "module": "account",
                "action": "txlist",
                "address": address,
                "startblock": 0,
                "endblock": 99_999_999,
                "sort": "desc",
                "apikey": api_key,
            }
            response = get_with_retry(self._session, self._config["base_url"], params=params_native)
            payload = response.json()
            # Etherscan reports a rate limit as HTTP 200 with status "0" and
            # an empty-looking result. Left undetected the tracer would read
            # that as "this wallet sent nothing" - turning a throttle into a
            # finding about the wallet, which is precisely the confusion this
            # codebase works to avoid everywhere else.
            if _is_rate_limited(payload):
                self._keys.penalise(api_key)
                raise RuntimeError(
                    f"{self.chain.value} explorer rate limit reached "
                    f"({payload.get('result') or payload.get('message')})"
                )
            results = payload.get("result") or []
            if isinstance(results, list):
                for tx in results:
                    if tx.get("isError") not in ("0", None):
                        continue
                    from_addr = (tx.get("from") or "").lower()
                    if from_addr != address.lower():
                        continue
                    to_addr = (tx.get("to") or "").lower()
                    if not to_addr:
                        continue
                    try:
                        value = int(tx["value"]) / (10**decimals)
                    except (KeyError, ValueError):
                        continue
                    if value <= 0:
                        continue
                    tx_hash = tx.get("hash", "")
                    seen_tx_hashes.add(tx_hash)
                    transfers.append(
                        Transfer(
                            tx_hash=tx_hash,
                            chain=self.chain,
                            from_address=from_addr,
                            to_address=to_addr,
                            value=value,
                            timestamp=int(tx.get("timeStamp", 0)),
                        )
                    )
                    if len(transfers) >= limit:
                        break
        except Exception:
            pass

        # 2. ERC-20 Token transfers (USDT, USDC, DAI, etc.)
        if len(transfers) < limit:
            try:
                params_token = {
                    "module": "account",
                    "action": "tokentx",
                    "address": address,
                    "startblock": 0,
                    "endblock": 99_999_999,
                    "sort": "desc",
                    "apikey": api_key,
                }
                response = get_with_retry(self._session, self._config["base_url"], params=params_token)
                token_results = response.json().get("result") or []
                if isinstance(token_results, list):
                    for tx in token_results:
                        if tx.get("isError") not in ("0", None):
                            continue
                        from_addr = (tx.get("from") or "").lower()
                        if from_addr != address.lower():
                            continue
                        to_addr = (tx.get("to") or "").lower()
                        if not to_addr:
                            continue
                        try:
                            token_dec = int(tx.get("tokenDecimal", 18))
                            value = int(tx["value"]) / (10**token_dec)
                        except (KeyError, ValueError):
                            continue
                        if value <= 0:
                            continue
                        tx_hash = tx.get("hash", "")
                        if tx_hash in seen_tx_hashes:
                            continue
                        seen_tx_hashes.add(tx_hash)
                        transfers.append(
                            Transfer(
                                tx_hash=tx_hash,
                                chain=self.chain,
                                from_address=from_addr,
                                to_address=to_addr,
                                value=value,
                                timestamp=int(tx.get("timeStamp", 0)),
                            )
                        )
                        if len(transfers) >= limit:
                            break
            except Exception:
                pass

        # Sort combined transfers by timestamp descending
        transfers.sort(key=lambda t: t.timestamp, reverse=True)
        return transfers[:limit]
