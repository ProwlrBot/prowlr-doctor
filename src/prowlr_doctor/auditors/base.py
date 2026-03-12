"""BaseAuditor ABC."""
from __future__ import annotations

from abc import ABC, abstractmethod

from prowlr_doctor.models import EnvironmentSnapshot, Finding


class BaseAuditor(ABC):
    """All auditors implement this interface."""

    @abstractmethod
    def audit(self, env: EnvironmentSnapshot) -> list[Finding]:
        """Run audit checks and return findings. Must not raise."""
        ...
