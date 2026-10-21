"""Mock of M9: fixed data in the real shape. Served while USE_MOCKS=true (or M09_USE_MOCK=true)."""


def render(req: dict) -> dict:
    p = req.get("payload") or {}
    return {
        "result": {
            "glb_url": None,
            "cached": False,
            "seconds": 0.0,
            "body": {"chest_cm": 91.0, "waist_cm": 70.5, "hips_cm": 98.0},
            "fit": {"avatar_height_cm": p.get("height_cm", 165), "avatar_weight_kg": p.get("weight_kg", 60)},
            "garments": [f"garment_{x}" for x in p.get("piece_ids", [])],
            "sizing": {},
        },
        "mocked": True,
    }
