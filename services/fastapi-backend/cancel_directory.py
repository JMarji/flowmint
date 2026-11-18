"""Lookup of how-to-cancel info for common subscription merchants.

Data lives in data/cancel_directory.json so it can be reviewed and extended without code changes.
"""
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus

_PATH = Path(__file__).parent / "data" / "cancel_directory.json"


@lru_cache(maxsize=1)
def _compiled() -> List[Tuple[int, re.Pattern, Dict[str, Any]]]:
    """(alias length, whole-word pattern, service) for every alias, longest first."""
    services = json.loads(_PATH.read_text())["services"]
    out = []
    for svc in services:
        for alias in svc["aliases"]:
            a = alias.lower().strip()
            # Whole-word match so short aliases ("nyt", "hbo") don't hit inside other words.
            pattern = re.compile(r"(?<![a-z0-9])" + re.escape(a) + r"(?![a-z0-9])")
            out.append((len(a), pattern, svc))
    out.sort(key=lambda x: x[0], reverse=True)
    return out


def lookup(*names: Optional[str]) -> Dict[str, Any]:
    """Best match across the given merchant name / description strings, else a search fallback."""
    haystacks = [n.lower() for n in names if n]
    for _, pattern, svc in _compiled():
        if any(pattern.search(h) for h in haystacks):
            return {
                "matched": True,
                "id": svc["id"],
                "name": svc["name"],
                "via": bool(svc.get("via")),
                "url": svc.get("url"),
                "steps": svc.get("steps") or [],
                "notes": svc.get("notes"),
                "search_url": None,
            }
    label = next((n for n in names if n), "subscription")
    return {
        "matched": False,
        "id": None,
        "name": label,
        "via": False,
        "url": None,
        "steps": [],
        "notes": None,
        "search_url": "https://www.google.com/search?q=" + quote_plus(f"how to cancel {label} subscription"),
    }
