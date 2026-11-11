"""
Content Engine Autonomous Agentic System
Includes:
- Scout Agent (Viral research & angle finder)
- Story Architect Agent (Looped Arc 5-phase scriptwriter)
- BRoll Agent (Visual & stock footage sourcing)
- Voice Agent (Neural voiceover & timestamp extraction)
- Foley Agent (Sound design & dry punchline cutout)
- QC Assembler Agent (Master video assembly, subtitle burn & verification)
- Orchestrator (Unified pipeline coordinator)
"""

from content_engine.agents.orchestrator import (
    run_option_a_pipeline,
    run_option_b_roadmap,
    run_option_b_transform
)

__all__ = [
    "run_option_a_pipeline",
    "run_option_b_roadmap",
    "run_option_b_transform"
]
