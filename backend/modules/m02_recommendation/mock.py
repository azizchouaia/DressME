"""Week-1 mock of M2: fixed data in the agreed shape. Replace by service.py, same signatures."""

def recommend(req: dict) -> dict:
    return {"result": {"todo": "M2 recommend mock"}, "mocked": True}
