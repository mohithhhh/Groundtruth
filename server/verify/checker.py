"""Deterministic claim verifier. No LLM involved -- every check here is
plain code, per CLAUDE.md: "the numeric check is always code."

A claim's `path` is resolved against the *full* stored tool_result entry
(which has keys tool_name, params, data, created_at) -- so a path like
"data[0].ward_name" means entry["data"][0]["ward_name"], matching the
example in CLAUDE.md Section 6, Phase 2, item 4.
"""

import re
from dataclasses import dataclass, field

_PATH_TOKEN_RE = re.compile(r"([^.\[\]]+)|\[(\d+)\]")
_PLACEHOLDER_RE = re.compile(r"\{(c\d+)\}")
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")

_CELSIUS_ABS_TOLERANCE = 0.05
_RELATIVE_TOLERANCE = 0.005  # 0.5%


class PathResolutionError(Exception):
    pass


def resolve_path(entry: dict, path: str):
    tokens = _PATH_TOKEN_RE.findall(path)
    current = entry
    for key, idx in tokens:
        try:
            if key:
                current = current[key]
            else:
                current = current[int(idx)]
        except (KeyError, IndexError, TypeError) as e:
            raise PathResolutionError(f"could not resolve '{path}' at segment '{key or idx}': {e}")
    return current


def _normalize_path(entry: dict, path: str) -> str:
    """Gemini's function-calling convention wraps a tool's return value as
    {tool_name}_response in the model's own context, so it sometimes writes
    that prefix into the claim path even though our stored entry has no such
    key. Stripping it doesn't weaken verification -- the actual value check
    below still runs against the real stored data either way."""
    prefix = f"{entry.get('tool_name')}_response."
    if path.startswith(prefix):
        return path[len(prefix):]
    return path


def _decimals(value: float) -> int:
    s = repr(float(value))
    return len(s.split(".")[1]) if "." in s else 0


def _is_celsius(unit: str | None) -> bool:
    return bool(unit) and "c" in unit.lower() and "°" in unit


def verify_number_claim(claim: dict, resolved) -> tuple[bool, str | None]:
    if claim.get("value") is None:
        return False, "claim has kind 'number' but no value set"
    try:
        resolved_value = float(resolved)
    except (TypeError, ValueError):
        return False, f"resolved value {resolved!r} is not numeric"

    decimals = _decimals(claim["value"])
    displayed_actual = round(resolved_value, decimals)
    displayed_claim = round(claim["value"], decimals)

    if _is_celsius(claim.get("unit")):
        ok = abs(displayed_actual - displayed_claim) <= _CELSIUS_ABS_TOLERANCE
    else:
        denom = abs(displayed_actual) if displayed_actual != 0 else 1e-9
        ok = abs(displayed_actual - displayed_claim) / denom <= _RELATIVE_TOLERANCE

    if ok:
        return True, None
    return False, f"claim says {displayed_claim}{claim.get('unit', '')}, tool result gives {displayed_actual}{claim.get('unit', '')}"


def verify_entity_claim(claim: dict, resolved) -> tuple[bool, str | None]:
    if resolved is None:
        return False, "resolved value is None"
    ok = str(resolved).strip().lower() == str(claim["text"]).strip().lower()
    if ok:
        return True, None
    return False, f"claim says '{claim['text']}', tool result gives '{resolved}'"


@dataclass
class VerificationResult:
    narrative: str
    verified_claims: list[dict] = field(default_factory=list)
    removed: list[dict] = field(default_factory=list)

    @property
    def verified(self) -> int:
        return len(self.verified_claims)

    @property
    def total(self) -> int:
        return self.verified + len(self.removed)

    def as_dict(self) -> dict:
        return {"verified": self.verified, "total": self.total, "removed": self.removed}


def verify_answer(narrative: str, claims: list[dict], lookup_tool_result) -> VerificationResult:
    """lookup_tool_result(tool_result_id) -> the stored entry dict, or None.

    Every {cN} placeholder in the narrative must map to a claim; failed or
    unmapped claims are blanked out of the narrative and recorded in
    `removed`. Every number-looking token outside a placeholder is flagged
    the same way (it cannot be traced to a tool result) -- see
    docs/DECISIONS.md for the "removed" text is not rewritten" simplification.
    """
    claims_by_id = {c["id"]: c for c in claims}
    result = VerificationResult(narrative=narrative)
    rendered = narrative

    for placeholder_id in _PLACEHOLDER_RE.findall(narrative):
        claim = claims_by_id.get(placeholder_id)
        placeholder = "{" + placeholder_id + "}"
        if claim is None:
            result.removed.append({"id": placeholder_id, "reason": "no matching claim"})
            rendered = rendered.replace(placeholder, "")
            continue

        entry = lookup_tool_result(claim["tool_result_id"])
        if entry is None:
            result.removed.append({"id": placeholder_id, "reason": "unknown tool_result_id"})
            rendered = rendered.replace(placeholder, "")
            continue

        try:
            resolved = resolve_path(entry, _normalize_path(entry, claim["path"]))
        except PathResolutionError as e:
            result.removed.append({"id": placeholder_id, "reason": str(e)})
            rendered = rendered.replace(placeholder, "")
            continue

        if claim["kind"] == "number":
            ok, reason = verify_number_claim(claim, resolved)
        elif claim["kind"] == "entity":
            ok, reason = verify_entity_claim(claim, resolved)
        else:
            ok, reason = False, f"unknown claim kind '{claim['kind']}'"

        if ok:
            result.verified_claims.append(claim)
            rendered = rendered.replace(placeholder, claim["text"])
        else:
            result.removed.append({"id": placeholder_id, "reason": reason})
            rendered = rendered.replace(placeholder, "")

    # Stray numbers: any digit sequence in the ORIGINAL narrative that wasn't
    # inside a {cN} placeholder has no citation at all.
    narrative_without_placeholders = _PLACEHOLDER_RE.sub("", narrative)
    for match in _NUMBER_RE.finditer(narrative_without_placeholders):
        result.removed.append({"id": None, "reason": f"stray number '{match.group()}' outside any claim placeholder"})

    result.narrative = re.sub(r"\s{2,}", " ", rendered).strip()
    return result
