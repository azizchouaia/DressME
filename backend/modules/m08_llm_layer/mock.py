"""Week-1 mock of M8: fixed data in the agreed shape. Replace by service.py, same signatures."""

def parse(req: dict) -> dict:
    return {"result": {"todo": "M8 parse mock"}, "mocked": True}

def explain(req: dict) -> dict:
    return {"result": {"todo": "M8 explain mock"}, "mocked": True}
