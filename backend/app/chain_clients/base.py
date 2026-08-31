from dataclasses import dataclass
from enum import Enum


class Chain(str, Enum):
    ETHEREUM = "ethereum"
    BSC = "bsc"
    POLYGON = "polygon"
    BITCOIN = "bitcoin"


EVM_CHAINS = {Chain.ETHEREUM, Chain.BSC, Chain.POLYGON}


@dataclass(frozen=True)
class Transfer:
    """One outgoing transfer of funds from an address, normalised across chains."""

    tx_hash: str
    chain: Chain
    from_address: str
    to_address: str
    value: float  # in the chain's native unit (ETH / BNB / MATIC / BTC)
    timestamp: int  # unix seconds


class ChainClient:
    """Common interface every chain client implements."""

    chain: Chain

    def get_outgoing_transfers(self, address: str) -> list[Transfer]:
        raise NotImplementedError
