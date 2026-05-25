"""
Noesis Skill Forge — Procedural memory generation.

Takes recurring failure patterns from the ProjectRetrospective
and forges them into reusable Skills that prevent the same
failure from happening again.

Skill lifecycle: PROPOSED → VALIDATING → PROMOTED → DEPRECATED
"""

from noesis.forge.skill_forge import SkillForge

__all__ = ["SkillForge"]
