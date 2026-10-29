"""Week-1 envelope mock of M5, kept for the BO8 orchestrator tool (agent.py calls mock.profile).

The real M5 endpoints are all served by service.py (see router.py); POST /m05/profile answers with the
real profile in the same envelope.
"""


def profile(req: dict) -> dict:
    return {
        "result": {
            "user_id": req.get("user_id"),
            "style_mix": {"classic": 0.42, "casual": 0.35, "minimalist": 0.23},
            "top_families": ["elegant", "casual"],
            "onboarded": True,
        },
        "mocked": True,
    }


def gaps(req: dict) -> dict:
    return {"result": {"todo": "M5 gaps mock"}, "mocked": True}
