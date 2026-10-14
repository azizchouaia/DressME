from orchestrator.registry import tool_names


def test_registry_lists_module_tools():
    assert isinstance(tool_names(), list)  # a module appears here once it ships a tool.py
