import json
from functools import lru_cache
from pathlib import Path

from app.chain_clients.base import normalize_address

_SEED_FILE = Path(__file__).parent / "seed_labels.json"


@lru_cache
def load_labels() -> dict[tuple[str, str], dict]:
    """Returns {(chain, normalized_address): {type, name, source}}."""
    data = json.loads(_SEED_FILE.read_text())
    labels: dict[tuple[str, str], dict] = {}
    for entry in data["labels"]:
        key = (entry["chain"], normalize_address(entry["address"]))
        labels[key] = {
            "type": entry["type"],
            "name": entry["name"],
            "source": entry.get("source", ""),
        }
    return labels


def lookup_label(chain: str, address: str) -> dict | None:
    return load_labels().get((chain, normalize_address(address)))
