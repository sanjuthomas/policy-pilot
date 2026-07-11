#!/usr/bin/env python3
"""Fail when lifecycle allow rules drift from action_catalog gate_predicates.

Single source of truth for chat summaries is action_catalog in policy_catalog.rego.
lifecycle.rego must:
  * use catalog_role_ok / catalog_group_ok for every catalogued action
  * reference every gate_predicate listed for that action

policy_summary.rego must only derive from action_catalog (no hardcoded role strings).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
POLICIES = Path(os.environ.get("POLICIES_DIR", str(ROOT / "policies")))

DOMAINS = (
    ("payment", POLICIES / "payment"),
    ("instruction", POLICIES / "instruction"),
)

_ACTION_KEY = re.compile(r'^\t"(?P<action>[A-Z_]+)": \{', re.M)
_ROLE = re.compile(r'"role"\s*:\s*"(?P<role>[^"]+)"')
_GROUP = re.compile(r'"group"\s*:\s*"(?P<group>[^"]+)"')
_GATE_BLOCK = re.compile(
    r'"gate_predicates"\s*:\s*\[(?P<body>.*?)\]',
    re.S,
)
_QUOTED = re.compile(r'"([^"]+)"')


def _slice_object_body(text: str, start: int) -> str:
    """Return text inside `{...}` starting at ``start`` (index of '{')."""
    assert text[start] == "{"
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : index]
    raise ValueError("unbalanced braces while parsing action_catalog")


def parse_action_catalog(catalog_text: str) -> dict[str, dict[str, object]]:
    marker = "action_catalog :="
    marker_at = catalog_text.find(marker)
    if marker_at < 0:
        raise ValueError("action_catalog not found")
    brace_at = catalog_text.find("{", marker_at)
    catalog_body = _slice_object_body(catalog_text, brace_at)

    actions: dict[str, dict[str, object]] = {}
    for match in _ACTION_KEY.finditer(catalog_body):
        action = match.group("action")
        body_start = catalog_body.find("{", match.end() - 1)
        body = _slice_object_body(catalog_body, body_start)
        role_match = _ROLE.search(body)
        if not role_match:
            raise ValueError(f"{action}: missing role")
        group_match = _GROUP.search(body)
        gate_match = _GATE_BLOCK.search(body)
        predicates = _QUOTED.findall(gate_match.group("body")) if gate_match else []
        actions[action] = {
            "role": role_match.group("role"),
            "group": group_match.group("group") if group_match else None,
            "gate_predicates": predicates,
        }
    if not actions:
        raise ValueError("no actions parsed from action_catalog")
    return actions


def allow_block_for(lifecycle_text: str, action: str) -> str | None:
    needle = f'input.action == "{action}"'
    start = lifecycle_text.find(needle)
    if start < 0:
        return None
    # Walk back to the enclosing `allow if {`
    allow_at = lifecycle_text.rfind("allow if {", 0, start)
    if allow_at < 0:
        allow_at = lifecycle_text.rfind("allow if{", 0, start)
    if allow_at < 0:
        return None
    brace_at = lifecycle_text.find("{", allow_at)
    return _slice_object_body(lifecycle_text, brace_at)


def validate_domain(domain: str, directory: Path) -> list[str]:
    errors: list[str] = []
    catalog_path = directory / "policy_catalog.rego"
    lifecycle_path = directory / "lifecycle.rego"
    summary_path = directory / "policy_summary.rego"

    for path in (catalog_path, lifecycle_path, summary_path):
        if not path.is_file():
            errors.append(f"{domain}: missing {path.name}")
    if errors:
        return errors

    catalog = parse_action_catalog(catalog_path.read_text(encoding="utf-8"))
    lifecycle = lifecycle_path.read_text(encoding="utf-8")
    summary = summary_path.read_text(encoding="utf-8")

    if "action_catalog" not in summary:
        errors.append(f"{domain}: policy_summary.rego does not reference action_catalog")

    # Hardcoded role literals in summary indicate drift back to a duplicate catalog.
    for action, meta in catalog.items():
        role = str(meta["role"])
        if f'"{role}"' in summary:
            errors.append(
                f"{domain}: policy_summary.rego hardcodes role {role}; "
                "derive it from action_catalog instead"
            )

    for action, meta in catalog.items():
        block = allow_block_for(lifecycle, action)
        if block is None:
            errors.append(f"{domain}: lifecycle.rego has no allow rule for {action}")
            continue
        if "catalog_role_ok" not in block:
            errors.append(
                f"{domain}: {action} allow rule must use catalog_role_ok "
                f"(catalog role={meta['role']})"
            )
        if meta["group"] is not None and "catalog_group_ok" not in block:
            errors.append(
                f"{domain}: {action} allow rule must use catalog_group_ok "
                f"(catalog group={meta['group']})"
            )
        # Avoid re-introducing hardcoded identity gates in catalogued allow rules.
        if f'has_role("{meta["role"]}")' in block:
            errors.append(
                f"{domain}: {action} allow rule hardcodes has_role(\"{meta['role']}\"); "
                "use catalog_role_ok"
            )
        if meta["group"] and f'in_group("{meta["group"]}")' in block:
            errors.append(
                f"{domain}: {action} allow rule hardcodes in_group(\"{meta['group']}\"); "
                "use catalog_group_ok"
            )
        for predicate in meta["gate_predicates"]:
            if str(predicate) not in block:
                errors.append(
                    f"{domain}: {action} allow rule missing gate_predicate "
                    f"'{predicate}' listed in action_catalog"
                )

    return errors


def main() -> int:
    all_errors: list[str] = []
    for domain, directory in DOMAINS:
        all_errors.extend(validate_domain(domain, directory))

    if all_errors:
        print("policy catalog drift detected:", file=sys.stderr)
        for error in all_errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print("policy catalog aligned with lifecycle for payment and instruction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
