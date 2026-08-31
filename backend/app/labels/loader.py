import json
from functools import lru_cache
from pathlib import Path

_SEED_FILE = Path(__file__).parent / "seed_labels.json"


@lru_cache
def load_labels() -> dict[tuple[str, str], dict]:
    """Returns {(chain, lowercase_address): {type, name, source}}."""
    data = json.loads(_SEED_FILE.read_text())
    labels: dict[tuple[str, str], dict] = {}
    for entry in data["labels"]:
        key = (entry["chain"], entry["address"].lower())
        labels[key] = {
            "type": entry["type"],
            "name": entry["name"],
            "source": entry.get("source", ""),
        }
    return labels


def lookup_label(chain: str, address: str) -> dict | None:
    return load_labels().get((chain, address.lower()))
