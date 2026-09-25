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
_NUMBER_RE = re.compile(r"-?\d+(?:,\d{2,3})*(?:\.\d+)?")
# A stray number is cut together with a unit right after it, so "by 3.1 °C"
# does not leave a dangling "°C" behind.
_UNIT_AFTER = r"(?:\s?(?:person-°C|°\s?C|%))?"
_STRAY_RE = re.compile(_NUMBER_RE.pattern + _UNIT_AFTER)

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
    below still runs against the real stored data either way. The prefix
    is the Python function's name, which can differ from the stored
    tool_name (the plan_budget tool records a budget_plan result), so any
    single "<name>_response." prefix is stripped."""
    return re.sub(r"^\w+_response\.", "", path)


def resolve_claim_path(entry: dict, path: str):
    """The path as written; else under "data" (the model sometimes drops
    that level); else, when its last key is one of the call's parameters,
    that parameter -- a tool called with year=2025 returns 2025 data, so the
    year is traceable to the recorded call even though no row repeats it.
    The value check that follows still runs against whatever resolves."""
    try:
        return resolve_path(entry, path)
    except PathResolutionError as first_error:
        try:
            return resolve_path(entry, "data." + path)
        except PathResolutionError:
            last = _PATH_TOKEN_RE.findall(path)[-1][0] if _PATH_TOKEN_RE.findall(path) else ""
            if last and last in (entry.get("params") or {}):
                return entry["params"][last]
            raise first_error


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

    # "50 crore" with unit "crore rupees" states 500,000,000.
    unit = (claim.get("unit") or "").lower()
    scale = 1e7 if "crore" in unit else 1e5 if "lakh" in unit else 1
    claim = {**claim, "value": float(claim["value"]) * scale}

    # Whole-number sources (years, ranks, counts, people, rupees) must match
    # exactly: 0.5% of 2025 would otherwise accept 2016 as 2025.
    if resolved_value.is_integer():
        if float(claim["value"]) == resolved_value:
            return True, None
        return False, f"claim says {claim['value']}, tool result gives {resolved_value:g}"

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
    # Same text, but verified claims keep their {cN} token so a UI can render
    # each one as a traceable figure chip; failed ones are blanked like above.
    template: str = ""
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

    # Stray numbers: any digit sequence outside a {cN} placeholder has no
    # citation at all. Flag it and cut it from what the reader sees.
    parts = _PLACEHOLDER_RE.split(narrative)
    for i in range(0, len(parts), 2):  # even indexes are text between placeholders
        for match in _NUMBER_RE.finditer(parts[i]):
            result.removed.append({"id": None, "reason": f"stray number '{match.group()}' outside any claim placeholder"})
        parts[i] = _STRAY_RE.sub("", parts[i])
    for i in range(1, len(parts), 2):
        parts[i] = "{" + parts[i] + "}"
    rendered = template = "".join(parts)

    for placeholder_id in _PLACEHOLDER_RE.findall(narrative):
        claim = claims_by_id.get(placeholder_id)
        placeholder = "{" + placeholder_id + "}"
        if claim is None:
            result.removed.append({"id": placeholder_id, "reason": "no matching claim"})
            rendered = _cut(placeholder, rendered)
            template = _cut(placeholder, template)
            continue

        entry = lookup_tool_result(claim["tool_result_id"])
        if entry is None:
            result.removed.append({"id": placeholder_id, "reason": "unknown tool_result_id"})
            rendered = _cut(placeholder, rendered)
            template = _cut(placeholder, template)
            continue

        try:
            resolved = resolve_claim_path(entry, _normalize_path(entry, claim["path"]))
        except PathResolutionError as e:
            result.removed.append({"id": placeholder_id, "reason": str(e)})
            rendered = _cut(placeholder, rendered)
            template = _cut(placeholder, template)
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
            rendered = _cut(placeholder, rendered)
            template = _cut(placeholder, template)

    result.narrative = _tidy(rendered)
    result.template = _tidy(template)
    return result


def _cut(placeholder: str, text: str) -> str:
    """Remove a failed claim's placeholder and any unit written after it."""
    return re.sub(re.escape(placeholder) + _UNIT_AFTER, "", text)


def _tidy(text: str) -> str:
    text = re.sub(r"\s{2,}", " ", text)
    return re.sub(r"\s+([.,;:])", r"\1", text).strip()
