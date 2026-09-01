import re
from typing import Any

# Regex patterns for blockchain addresses and identifiers
_EVM_REGEX = re.compile(r"\b(0x[a-fA-F0-9]{40})\b")
_BTC_BECH32_REGEX = re.compile(r"\b(bc1[a-zA-HJ-NP-Z0-9]{25,59})\b")
_BTC_LEGACY_REGEX = re.compile(r"\b([13][a-km-zA-HJ-NP-Z1-9]{25,34})\b")
_TRON_REGEX = re.compile(r"\b(T[a-zA-HJ-NP-Z0-9]{33})\b")

# Transactions & Financial identifiers
_EVM_TX_REGEX = re.compile(r"\b(0x[a-fA-F0-9]{64})\b")
_GENERIC_TX_REGEX = re.compile(r"\b([a-fA-F0-9]{64})\b")
_UPI_REGEX = re.compile(r"\b([a-zA-Z0-9.\-_]{2,256}@(okhdfcbank|okaxis|okicici|oksbi|paytm|ybl|ibl|axl|apl|upi))\b", re.IGNORECASE)
_COMPLAINT_REF_REGEX = re.compile(r"\b((?:NCRP|FIR|ACK|COMPLAINT|REF)[\/\-_:\s#]*[0-9A-Za-z\-_/]+)\b", re.IGNORECASE)

# Amounts & Currencies
_AMOUNT_REGEX = re.compile(
    r"(?:(?:Rs\.?|INR|₹|\$|USD)\s*([0-9,]+(?:\.[0-9]+)?)|([0-9,]+(?:\.[0-9]+)?)\s*(?:ETH|BTC|USDT|BNB|MATIC|TRX|SOL|INR|USD|Rupees))",
    re.IGNORECASE,
)


def parse_complaint_text(text: str) -> dict[str, Any]:
    """Extracts candidate wallet addresses, chains, tx hashes, UPI IDs,
    and financial entities from unformatted victim complaint narratives."""
    if not text:
        return {
            "wallets": [],
            "tx_hashes": [],
            "upi_ids": [],
            "amounts": [],
            "complaint_refs": [],
            "suggested_chain": "ethereum",
            "extracted_count": 0,
        }

    wallets = []
    seen_addresses = set()

    # 1. EVM Addresses (Ethereum / BSC / Polygon)
    for match in _EVM_REGEX.finditer(text):
        addr = match.group(1)
        if addr.lower() not in seen_addresses:
            seen_addresses.add(addr.lower())
            # Check context for chain hints
            surrounding = text[max(0, match.start() - 40) : min(len(text), match.end() + 40)].lower()
            chain_hint = "ethereum"
            if "bsc" in surrounding or "binance" in surrounding or "bnb" in surrounding:
                chain_hint = "bsc"
            elif "polygon" in surrounding or "matic" in surrounding:
                chain_hint = "polygon"
            wallets.append({
                "address": addr,
                "chain": chain_hint,
                "format": "EVM (Ethereum/BSC/Polygon)",
                "confidence": 0.95,
            })

    # 2. Bitcoin Addresses
    for match in _BTC_BECH32_REGEX.finditer(text):
        addr = match.group(1)
        if addr not in seen_addresses:
            seen_addresses.add(addr)
            wallets.append({
                "address": addr,
                "chain": "bitcoin",
                "format": "Bitcoin (Bech32)",
                "confidence": 0.99,
            })

    for match in _BTC_LEGACY_REGEX.finditer(text):
        addr = match.group(1)
        if addr not in seen_addresses:
            seen_addresses.add(addr)
            wallets.append({
                "address": addr,
                "chain": "bitcoin",
                "format": "Bitcoin (Legacy/P2SH)",
                "confidence": 0.85,
            })

    # 3. Tron Addresses
    for match in _TRON_REGEX.finditer(text):
        addr = match.group(1)
        if addr not in seen_addresses:
            seen_addresses.add(addr)
            wallets.append({
                "address": addr,
                "chain": "tron",
                "format": "Tron (TRC-20 / Base58)",
                "confidence": 0.90,
            })

    # 4. Tx Hashes
    tx_hashes = []
    seen_txs = set()
    for match in _EVM_TX_REGEX.finditer(text):
        tx = match.group(1)
        if tx.lower() not in seen_txs:
            seen_txs.add(tx.lower())
            tx_hashes.append(tx)

    for match in _GENERIC_TX_REGEX.finditer(text):
        tx = match.group(1)
        if tx.lower() not in seen_txs and not any(tx.lower() in w["address"].lower() for w in wallets):
            seen_txs.add(tx.lower())
            tx_hashes.append(tx)

    # 5. UPI IDs
    upi_ids = list({match.group(1).lower() for match in _UPI_REGEX.finditer(text)})

    # 6. Complaint references
    complaint_refs = []
    for match in _COMPLAINT_REF_REGEX.finditer(text):
        ref = match.group(1).strip(" :-,")
        if len(ref) > 4 and ref not in complaint_refs:
            complaint_refs.append(ref)

    # 7. Amounts
    amounts = []
    for match in _AMOUNT_REGEX.finditer(text):
        matched_str = match.group(0).strip()
        if matched_str and matched_str not in amounts:
            amounts.append(matched_str)

    # Determine default suggested chain
    suggested_chain = "ethereum"
    if wallets:
        suggested_chain = wallets[0]["chain"]

    return {
        "wallets": wallets,
        "tx_hashes": tx_hashes[:10],
        "upi_ids": upi_ids[:5],
        "amounts": amounts[:5],
        "complaint_refs": complaint_refs[:3],
        "suggested_chain": suggested_chain,
        "extracted_count": len(wallets),
    }
