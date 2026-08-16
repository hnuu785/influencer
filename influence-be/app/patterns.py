from __future__ import annotations

from typing import Any


ALLOWED_PATTERN_RIGHTS_BASES = {
    "licensed",
    "public_domain",
    "team_authored",
    "user_owned",
}


def validate_pattern_seed(seed: dict[str, Any]) -> dict[str, Any]:
    rights_basis = seed.get("rights_basis", "team_authored")
    if rights_basis not in ALLOWED_PATTERN_RIGHTS_BASES:
        raise ValueError(
            f"Pattern rights basis is not approved for RAG: {rights_basis}"
        )
    return {**seed, "rights_basis": rights_basis}
