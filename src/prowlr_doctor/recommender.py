"""Profile-aware recommendation engine."""
from __future__ import annotations

from prowlr_doctor.models import Finding, Recommendations

Profile = str

# disposition: "disable" | "review" | "keep" | "condense"
# category → profile → disposition
_RULES: dict[str, dict[str, str]] = {
    "duplicate": {
        "developer": "disable",
        "security": "disable",
        "minimal": "disable",
        "agent-builder": "disable",
        "research": "disable",
    },
    "token-waste": {
        "developer": "review",
        "security": "disable",
        "minimal": "disable",
        "agent-builder": "keep",
        "research": "keep",
    },
    "security": {
        "developer": "disable",
        "security": "disable",
        "minimal": "disable",
        "agent-builder": "disable",
        "research": "disable",
    },
    "conflict": {
        "developer": "review",
        "security": "disable",
        "minimal": "disable",
        "agent-builder": "review",
        "research": "review",
    },
    "stale": {
        "developer": "review",
        "security": "disable",
        "minimal": "disable",
        "agent-builder": "review",
        "research": "review",
    },
    "verbosity": {
        "developer": "keep",
        "security": "condense",
        "minimal": "condense",
        "agent-builder": "keep",
        "research": "keep",
    },
}


def recommend(findings: list[Finding], profile: Profile = "developer") -> Recommendations:
    rec = Recommendations(profile=profile)
    for finding in findings:
        disposition = _RULES.get(finding.category, {}).get(profile, "review")
        if disposition == "disable":
            rec.disable.append(finding)
        elif disposition == "keep":
            rec.keep.append(finding)
        elif disposition == "condense":
            rec.condense.append(finding)
        else:
            rec.review.append(finding)
    return rec
