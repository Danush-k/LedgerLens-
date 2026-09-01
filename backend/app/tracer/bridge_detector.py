from app.labels.loader import lookup_label


KNOWN_BRIDGES_DEXES = {
    "stargate", "thorchain", "hop_protocol", "synapse", "multichain", "celer",
    "uniswap", "pancakeswap", "sushiswap", "changenow", "fixedfloat", "sidechip"
}


def detect_cross_chain_swaps(chain: str, edges: list[dict]) -> list[dict]:
    """Scans transfers in a case graph for interactions with decentralized exchanges,
    cross-chain bridges, or non-custodial instant swap routers.
    """
    detected_swaps: list[dict] = []
    
    for edge in edges:
        target_addr = edge["target"].split(":")[-1] if ":" in edge["target"] else edge["target"]
        label = lookup_label(chain, target_addr)
        if label:
            label_type = label.get("type", "")
            label_name = label.get("name", "").lower()
            
            is_bridge_or_dex = (
                label_type in ("bridge", "mixer", "dex") or
                any(b in label_name for b in KNOWN_BRIDGES_DEXES)
            )

            if is_bridge_or_dex:
                detected_swaps.append({
                    "tx_hash": edge.get("tx_hash"),
                    "source": edge.get("source"),
                    "target": edge.get("target"),
                    "protocol_name": label.get("name"),
                    "type": label_type,
                    "amount": edge.get("value"),
                    "timestamp": edge.get("timestamp"),
                    "hop": edge.get("hop"),
                    "note": f"Transfer routed through {label.get('name')} ({label_type.upper()}). Funds may be obfuscated or bridged."
                })

    return detected_swaps
