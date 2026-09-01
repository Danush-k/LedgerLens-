import json
from functools import lru_cache
from pathlib import Path

from app.chain_clients.base import normalize_address

_SEED_FILE = Path(__file__).parent / "seed_labels.json"


@lru_cache
def _get_raw_data() -> dict:
    return json.loads(_SEED_FILE.read_text())


@lru_cache
def load_labels() -> dict[tuple[str, str], dict]:
    """Returns {(chain, normalized_address): {type, name, vasp_key, source}}."""
    data = _get_raw_data()
    labels: dict[tuple[str, str], dict] = {}
    for entry in data.get("labels", []):
        key = (entry["chain"], normalize_address(entry["address"]))
        labels[key] = {
            "type": entry["type"],
            "name": entry["name"],
            "vasp_key": entry.get("vasp_key"),
            "source": entry.get("source", ""),
        }
    return labels


def lookup_label(chain: str, address: str) -> dict | None:
    return load_labels().get((chain, normalize_address(address)))


@lru_cache
def get_vasp_directory() -> dict[str, dict]:
    """Returns directory of known VASPs with law enforcement compliance contacts."""
    data = _get_raw_data()
    return data.get("vasp_directory", {})


def get_vasp_metadata(name_or_key: str | None) -> dict | None:
    """Finds VASP contact metadata by key or partial exchange name."""
    if not name_or_key:
        return None
    directory = get_vasp_directory()
    if name_or_key in directory:
        return directory[name_or_key]
    
    # Try fuzzy matching by name prefix
    clean_name = name_or_key.lower()
    for key, meta in directory.items():
        if key.lower() in clean_name or clean_name in key.lower():
            return meta
    return {
        "full_name": name_or_key,
        "compliance_email": "lawenforcement-compliance@vasp.internal",
        "portal_url": "https://vasp.internal/law-enforcement",
        "jurisdiction": "International / Unregistered",
        "fiu_registered": False,
    }
