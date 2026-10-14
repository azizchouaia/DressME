"""Idea 9 — personalisation with a contextual bandit (simple reinforcement learning).

Each user gets their own 'strictness': a shift of the BUY/SKIP thresholds, chosen among ARMS.
Thompson sampling: each arm has a Beta(success, failure) belief per user; we sample, pick the best,
and update with the reward after the user tells us (or we observe) whether the advice was good.

Reward ideas (real app): user followed the advice AND (bought -> wore it >= 4 times in 2 months)
or (skipped -> did not come back to buy it). In this project we simulate users: python -m modules.m06_smartbuy.bandit
"""

import json
import random
from pathlib import Path

ARMS = [-10, -5, 0, 5, 10]  # negative = relaxed (BUY more easily), positive = strict
STATE = Path(__file__).resolve().parent.parent.parent.parent / "ml" / "data" / "bo5" / "bandit_state.json"


class PersonalThresholds:
    def __init__(self, path: Path | None = STATE, seed: int | None = None):
        self.path = path
        self.rng = random.Random(seed)
        self.state = json.loads(path.read_text()) if path and path.exists() else {}

    def _arms(self, user):
        return self.state.setdefault(user, {str(a): [1, 1] for a in ARMS})

    def choose(self, user: str) -> int:
        arms = self._arms(user)
        return max(ARMS, key=lambda a: self.rng.betavariate(*arms[str(a)]))

    def best(self, user: str) -> int:
        arms = self._arms(user)
        return max(ARMS, key=lambda a: arms[str(a)][0] / sum(arms[str(a)]))

    def update(self, user: str, arm: int, reward: bool) -> None:
        self._arms(user)[str(arm)][0 if reward else 1] += 1
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.state, indent=1))


def simulate(rounds: int = 300, seed: int = 1):
    """3 simulated shoppers with a hidden strictness. The bandit must discover it from rewards only."""
    import asyncio

    from .agent import SmartBuyAgent
    from .pipeline.decide import decide

    agent = SmartBuyAgent({**SmartBuyAgent().config, "personalize": False})
    facts = [asyncio.run(agent.facts(c["id"], c.get("user_id", "usr_demo"), c.get("price_tnd", 80)))
             for c in agent.clients.candidates.values()]
    personas = {"relaxed shopper": -10, "average shopper": 0, "strict minimalist": 10}
    # keep the pieces where strictness changes the answer (elsewhere every arm gives the same advice)
    facts = [f for f in facts if len({decide(f, agent.config, agent.model, o)["verdict"] for o in ARMS}) > 1] or facts
    rng = random.Random(seed)
    pt = PersonalThresholds(path=None, seed=seed)
    print(f"{len(facts)} pieces where strictness matters, {rounds} rounds per persona")
    print(f"{'persona':20} {'hidden':>6} {'learned':>8} {'same advice':>12}  accepted: first 50 -> last 50")
    for name, hidden in personas.items():
        hits = []
        for _ in range(rounds):
            f = rng.choice(facts)
            arm = pt.choose(name)
            ours = decide(f, agent.config, agent.model, arm)["verdict"]
            theirs = decide(f, agent.config, agent.model, hidden)["verdict"]
            ok = ours == theirs if rng.random() > 0.1 else rng.random() < 0.5  # 10 % random mood
            pt.update(name, arm, ok)
            hits.append(ok)
        a, b = sum(hits[:50]) / 50, sum(hits[-50:]) / 50
        best = pt.best(name)
        same = sum(decide(f, agent.config, agent.model, best)["verdict"] == decide(f, agent.config, agent.model, hidden)["verdict"]
                   for f in facts) / len(facts)
        print(f"{name:20} {hidden:>6} {best:>8} {same:>12.0%}  {a:.0%} -> {b:.0%}")


if __name__ == "__main__":
    simulate()
