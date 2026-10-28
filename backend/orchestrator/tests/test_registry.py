from orchestrator.registry import tool_names


def test_smartbuy_is_a_tool():
    assert "m06_smartbuy" in tool_names()
