"""Feature vector of one (context, outfit) pair, from dressme_bandit.py. DIM follows the style list.

    context (C = 3 + #occasions): [temp, rain, occ_<o>..., weekend]           (baseline occasion = zeros)
    outfit  (S + 4)             : [style_mix (S)..., formality, warmth, novelty, taste_sim]
    x = [1, outfit, outer(context, style_mix).ravel(), temp * warmth]   -> 1 + (S+4) + C*S + 1
With 12 styles and occasions work / casual / event (+ sport baseline): C = 6, DIM = 90.
"""

from dataclasses import dataclass

import numpy as np

from .config import ContextConfig


@dataclass(frozen=True)
class Layout:
    styles: tuple[str, ...]
    occasions: tuple[str, ...]
    temp_center: float = 15.0
    temp_scale: float = 15.0

    @classmethod
    def build(cls, styles: list[str], ctx: ContextConfig) -> "Layout":
        return cls(tuple(styles), tuple(ctx.occasions), ctx.temp_center, ctx.temp_scale)

    @property
    def S(self) -> int:
        return len(self.styles)

    @property
    def context_names(self) -> list[str]:
        return ["temp", "rain", *(f"occ_{o}" for o in self.occasions), "weekend"]

    @property
    def C(self) -> int:
        return len(self.context_names)

    @property
    def dim(self) -> int:
        return 1 + (self.S + 4) + self.C * self.S + 1

    # --- indices -----------------------------------------------------------------------------------
    def style_index(self, style: str) -> int:
        return 1 + self.styles.index(style)

    @property
    def formality_index(self) -> int:
        return 1 + self.S

    @property
    def warmth_index(self) -> int:
        return 2 + self.S

    @property
    def novelty_index(self) -> int:
        return 3 + self.S

    @property
    def taste_index(self) -> int:
        return 4 + self.S

    def interaction_index(self, context_name: str, style: str) -> int:
        c = self.context_names.index(context_name)
        return 5 + self.S + c * self.S + self.styles.index(style)

    @property
    def temp_warmth_index(self) -> int:
        return self.dim - 1

    # --- vectors -----------------------------------------------------------------------------------
    def context_vector(self, temp_c: float, rain: bool, weekend: bool, occasion: str) -> np.ndarray:
        """`occasion` must already be canonical (aliases resolved); the baseline gives all-zero flags."""
        occ = [1.0 if occasion == o else 0.0 for o in self.occasions]
        temp = float(np.clip((temp_c - self.temp_center) / self.temp_scale, -1, 1))
        return np.array([temp, 1.0 if rain else 0.0, *occ, 1.0 if weekend else 0.0])

    def outfit_vector(
        self, style_mix, formality: float, warmth: float, novelty: float, taste_sim: float
    ) -> np.ndarray:
        mix = np.asarray(style_mix, dtype=float)
        if mix.shape != (self.S,):
            raise ValueError(f"style_mix has {mix.shape} values, expected ({self.S},)")
        return np.concatenate([mix, [formality, warmth, novelty, taste_sim]])

    def features(self, ctx: np.ndarray, out: np.ndarray) -> np.ndarray:
        style = out[: self.S]
        warmth = out[self.S + 1]
        interactions = np.outer(ctx, style).ravel()
        return np.concatenate([[1.0], out, interactions, [ctx[0] * warmth]])

    # --- readable names (explain) -----------------------------------------------------------------
    def describe(self, index: int, weight: float, labels: dict[str, str] | None = None) -> tuple[str, str]:
        """(feature key, readable sentence for this weight's sign)."""
        labels = labels or {}
        name = lambda s: labels.get(s, s.replace("_", " "))  # noqa: E731
        pos = weight >= 0
        S = self.S
        if index == 0:
            return "bias", "general mood (bias)"
        if 1 <= index <= S:
            s = self.styles[index - 1]
            return f"style:{s}", f"{'likes' if pos else 'avoids'} {name(s)} outfits"
        simple = {
            self.formality_index: (
                "formality",
                "prefers formal outfits" if pos else "prefers relaxed outfits",
            ),
            self.warmth_index: ("warmth", "prefers warm outfits" if pos else "prefers light outfits"),
            self.novelty_index: (
                "novelty",
                "likes pieces not worn for a while" if pos else "likes recently worn favourites",
            ),
            self.taste_index: (
                "taste_sim",
                "likes outfits close to their taste" if pos else "likes outfits far from their usual taste",
            ),
            self.temp_warmth_index: (
                "temp_x_warmth",
                "wants warm outfits when it's hot"
                if pos
                else "avoids warm outfits when it's hot (wants them when cold)",
            ),
        }
        if index in simple:
            return simple[index]
        k = index - (5 + S)
        c, s = self.context_names[k // S], self.styles[k % S]
        key = f"{c}x{s}"
        style = name(s)
        if c == "temp":
            return key, (
                f"more {style} when it's warm, less when cold"
                if pos
                else f"more {style} when it's cold, less when warm"
            )
        if c == "rain":
            return key, f"{'likes' if pos else 'avoids'} {style} when it rains"
        if c == "weekend":
            return key, f"{'likes' if pos else 'avoids'} {style} at the weekend"
        occasion = c.removeprefix("occ_")
        return key, f"{'likes' if pos else 'avoids'} {style} for {occasion}"
