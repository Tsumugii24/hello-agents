"""Backward-compatible entry points for the deep researcher agent."""

from __future__ import annotations

from .app.agents.deep_research_agent import DeepResearchAgent, run_deep_research

__all__ = ["DeepResearchAgent", "run_deep_research"]

