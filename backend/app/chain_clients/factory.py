from app.chain_clients.base import Chain, ChainClient, EVM_CHAINS
from app.chain_clients.bitcoin import BitcoinClient
from app.chain_clients.evm import EVMClient
from app.chain_clients.tron import TronClient


def get_chain_client(chain: Chain) -> ChainClient:
    if chain in EVM_CHAINS:
        return EVMClient(chain)
    if chain == Chain.BITCOIN:
        return BitcoinClient()
    if chain == Chain.TRON:
        return TronClient()
    raise ValueError(f"Unsupported chain: {chain}")
