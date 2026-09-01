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

    def get_co_spent_addresses(self, address: str) -> set[str]:
        """Common-input-ownership clustering signal. Only meaningful for
        UTXO chains (Bitcoin) - EVM's account model has no equivalent, so
        the default is "nothing to report" rather than every client having
        to implement a no-op."""
        return set()


import re

EVM_ADDRESS_REGEX = re.compile(r"^0x[a-fA-F0-9]{40}$")
BITCOIN_ADDRESS_REGEX = re.compile(
    r"^(1[1-9A-HJ-NP-Za-k-z]{25,34}|3[1-9A-HJ-NP-Za-k-z]{25,34}|bc1[0-9a-zA-Z]{38,59})$"
)
TRON_ADDRESS_REGEX = re.compile(r"^T[1-9A-HJ-NP-Za-k-z]{33}$")
SOLANA_ADDRESS_REGEX = re.compile(r"^[1-9A-HJ-NP-Za-k-z]{32,44}$")


def is_valid_address(address: str, chain: Chain | str) -> bool:
    """Validates that a wallet address adheres to strict chain-specific rules
    (start prefix, character set, and exact length boundaries).
    """
    addr = address.strip()
    chain_str = chain.value if isinstance(chain, Chain) else str(chain).lower()
    if chain_str in ("ethereum", "bsc", "polygon"):
        return bool(EVM_ADDRESS_REGEX.match(addr))
    if chain_str == "bitcoin":
        return bool(BITCOIN_ADDRESS_REGEX.match(addr))
    if chain_str == "tron":
        return bool(TRON_ADDRESS_REGEX.match(addr))
    if chain_str == "solana":
        return bool(SOLANA_ADDRESS_REGEX.match(addr))
    return len(addr) >= 10


def normalize_address(address: str) -> str:
    """Lowercase EVM (0x...) addresses for consistent matching/dedup - hex
    is case-insensitive there. Bitcoin base58 addresses are case-sensitive
    and bech32 ones are already lowercase by convention, so both are left
    untouched: lowercasing a base58 address silently turns it into a
    different, invalid-looking address.
    """
    return address.lower() if address.startswith("0x") else address
