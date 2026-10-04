import hashlib
import json


def hash_text(value: str) -> str:
    """Stable, fixed-length key for an arbitrary string."""
    return hashlib.sha256(value.encode()).hexdigest()


def hash_payload_input(list_1: list[str], list_2: list[str]) -> str:
    """Identify a payload by its input.

    The lists are hashed as an ordered pair: swapping them changes the interleaving
    and therefore the output. JSON gives an unambiguous encoding, so e.g. ["a,b"] and
    ["a", "b"] can never collide the way naive string joining would allow.
    """
    canonical = json.dumps([list_1, list_2], ensure_ascii=False, separators=(",", ":"))
    return hash_text(canonical)
