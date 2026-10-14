"""Tools the orchestrator (BO8) can call = every module that ships a tool.py. Nothing to edit by hand."""

import importlib
import pkgutil

import modules


def _tool_modules():
    for m in sorted(pkgutil.iter_modules(modules.__path__), key=lambda m: m.name):
        try:
            yield importlib.import_module(f"modules.{m.name}.tool")
        except ModuleNotFoundError as e:
            if e.name != f"modules.{m.name}.tool":
                raise


def get_tools():
    return [t.tool for t in _tool_modules()]


def tool_names() -> list[str]:
    return [m.name for m in pkgutil.iter_modules(modules.__path__)
            if importlib.util.find_spec(f"modules.{m.name}.tool") is not None]
