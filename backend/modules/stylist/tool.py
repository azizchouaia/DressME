"""The Stylist agent as a tool for the orchestrator (auto-discovered by orchestrator/registry.py)."""

from shared.action_agent import langchain_tool

from .agent import agent

tool = langchain_tool(agent)
