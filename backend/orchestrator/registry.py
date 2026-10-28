"""Tools the orchestrator (BO8) can call. Nothing to edit by hand.

One tool per AGENT: a module that ships a tool.py and whose identity card has no "agent" key.
A module whose card names an "agent" is a skill of that agent: the planner does not see it.
The tool takes the card's name, and its description starts with the card (when to use / not).
"""

import importlib
import pkgutil

import modules
from shared.agent_card import describe


def _import(name: str):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as e:
        if e.name != name:
            raise
        return None


def _agents():
    for m in sorted(pkgutil.iter_modules(modules.__path__), key=lambda m: m.name):
        tool_mod = _import(f"modules.{m.name}.tool")
        if tool_mod is None:
            continue
        ident = _import(f"modules.{m.name}.identity")
        card = getattr(ident, "CARD", None)
        if card and card.get("agent"):
            continue  # a skill: its agent calls it
        yield m.name, tool_mod.tool, card


def get_tools():
    tools = []
    for _, tool, card in _agents():
        if card:
            tool.name = card["name"]
            text = describe(card)
            if not (tool.description or "").startswith(text):
                tool.description = text + ("\n" + tool.description if tool.description else "")
        tools.append(tool)
    return tools


def cards() -> list[dict]:
    """Every agent's card (for the app and /chat/agents)."""
    return [card for _, _, card in _agents() if card]


def tool_names() -> list[str]:
    return [t.name for t in get_tools()]
