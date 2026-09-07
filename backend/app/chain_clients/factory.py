from app.chain_clients.base import Chain, ChainClient, EVM_CHAINS
from app.chain_clients.cache import CachedChainClient
from app.chain_clients.bitcoin import BitcoinClient
from app.chain_clients.evm import EVMClient
from app.chain_clients.tron import TronClient


def _build(chain: Chain) -> ChainClient:
    if chain in EVM_CHAINS:
        return EVMClient(chain)
    if chain == Chain.BITCOIN:
        return BitcoinClient()
    if chain == Chain.TRON:
        return TronClient()
    raise ValueError(f"Unsupported chain: {chain}")


def get_chain_client(chain: Chain, cached: bool = True) -> ChainClient:
    """The client for a chain, wrapped in the shared Redis cache by default.

    Caching is applied here rather than inside each client so every chain
    benefits without repeating the logic, and so tests can opt out with
    cached=False and exercise the real fetch path.
    """
    client = _build(chain)
    return CachedChainClient(client) if cached else client
