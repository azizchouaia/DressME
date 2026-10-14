"""Week-1 mock of M5: fixed data in the agreed shape. Replace by service.py, same signatures."""

def profile(req: dict) -> dict:
    return {"result": {"todo": "M5 profile mock"}, "mocked": True}

def feedback(req: dict) -> dict:
    return {"result": {"todo": "M5 feedback mock"}, "mocked": True}

def gaps(req: dict) -> dict:
    return {"result": {"todo": "M5 gaps mock"}, "mocked": True}
