"""
Noesis Reflection Engine — Self-scrutiny for AI agents.

Two-pass system:
  1. Session Autopsy — what happened, what worked, what failed
  2. Project Retrospective — roll episodes into patterns, detect recurring failures
"""

from noesis.reflection.autopsy import SessionAutopsy
from noesis.reflection.retrospective import ProjectRetrospective

__all__ = ["SessionAutopsy", "ProjectRetrospective"]
