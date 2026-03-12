"""Generate a PatchPlan from Recommendations — exact settings.json changes."""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

from prowlr_doctor import paths
from prowlr_doctor.models import EnvironmentSnapshot, FixAction, PatchPlan, Recommendations


def build_plan(
    env: EnvironmentSnapshot,
    rec: Recommendations,
) -> PatchPlan:
    """Build a PatchPlan from the disable list in Recommendations."""
    actions: list[FixAction] = []
    # Only auto-actionable (non-condense) disable actions, low-risk first
    for finding in rec.disable:
        if finding.fix_action and finding.fix_action.action_type != "condense":
            actions.append(finding.fix_action)

    # Compute settings diff
    before_settings = copy.deepcopy(env.settings)
    after_settings = copy.deepcopy(env.settings)
    for action in actions:
        if action.settings_path and len(action.settings_path) == 2:
            section, key = action.settings_path
            after_settings.setdefault(section, {})[key] = action.after

    savings = sum(
        f.tokens_wasted
        for f in rec.disable
        if f.fix_action and f.fix_action.action_type != "condense"
    )

    plan_path = paths.doctor_plan_path()

    return PatchPlan(
        version="1",
        generated_at=datetime.now(timezone.utc).isoformat(),
        profile=rec.profile,
        findings_count=len(rec.disable) + len(rec.review) + len(rec.keep) + len(rec.condense),
        actions=actions,
        estimated_savings=savings,
        settings_diff={"before": before_settings, "after": after_settings},
        plan_path=plan_path,
    )


def apply_plan(plan: PatchPlan) -> None:
    """Atomically apply a PatchPlan to ~/.claude/settings.json with backup."""
    sp = paths.settings_path()
    if not sp.exists():
        raise FileNotFoundError(f"settings.json not found at {sp}")

    # Backup
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = sp.with_suffix(f".json.bak.{ts}")
    backup.write_bytes(sp.read_bytes())

    try:
        new_settings = copy.deepcopy(plan.settings_diff["after"])
        tmp = sp.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(new_settings, indent=2))
        tmp.replace(sp)  # atomic rename
    except Exception:
        # Restore backup on failure
        backup.replace(sp)
        raise
