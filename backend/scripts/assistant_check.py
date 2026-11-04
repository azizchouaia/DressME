"""Rehearse the jury: run real conversations against the running backend and show who answered.

    cd backend
    python -m scripts.assistant_check                 # all scenarios
    python -m scripts.assistant_check --user usr_demo # another account

Needs the backend on http://localhost:8000 (python -m uvicorn api.main:app --port 8000).
Each line: the message, the agent that answered, the first words of the reply. ✗ = no agent / an error.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request

CONVERSATIONS = {
    "Smart Buy (EN, typos, ask then answer)": [
        "should i buy it? it's 320dt",
        "a blue costume",
        "yes, I need it for a wedding",
    ],
    "Smart Buy (FR / Tounsi)": [
        "est-ce que je dois acheter une robe rouge à 150 dt ?",
        "nechri pull noir b 80 dinars?",
    ],
    "Outfits": [
        "What should I wear tomorrow for work?",
        "another one",
        "why this outfit?",
        "chnowa nelbes ghodwa lel khedma",
    ],
    "Local shops": [
        "Find a white shirt in a shop in Tunis",
        "where can i buy black boots in sousse under 200 dt",
    ],
    "Wardrobe, style, challenges": [
        "Show my wardrobe",
        "I love oversize sweaters",
        "what is my style",
        "Show me the challenges",
    ],
    "Small talk": ["hello", "who are you?", "thanks!"],
}


def ask(base: str, user: str, session: str, message: str) -> dict:
    body = json.dumps({"user_id": user, "session_id": session, "message": message}).encode()
    req = urllib.request.Request(f"{base}/chat/message", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=240) as r:
        return json.loads(r.read())


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://localhost:8000")
    p.add_argument("--user", default="usr_demo")
    a = p.parse_args()
    bad = 0
    for title, turns in CONVERSATIONS.items():
        print(f"\n=== {title}")
        session = f"check-{int(time.time() * 1000)}"
        for m in turns:
            t0 = time.time()
            try:
                r = ask(a.base, a.user, session, m)
                agent, reply = r.get("last_agent") or "—", (r.get("question") or r.get("reply") or "").replace("\n", " ")
                ok = not r.get("error") and (agent != "—" or title == "Small talk" or "?" in reply)
            except Exception as e:  # noqa: BLE001
                agent, reply, ok = "ERROR", str(e), False
            bad += not ok
            print(f"{'✓' if ok else '✗'} {m!r:58} -> {agent:11} {time.time() - t0:5.1f}s  {reply[:110]}")
    print(f"\n{'All good' if not bad else f'{bad} turn(s) to look at'}")


if __name__ == "__main__":
    main()
