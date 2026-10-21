"""Real body (sex, height cm, weight kg) -> MPFB macro sliders (gender, height, weight), and back.

Uses the calibration grid measured on the MPFB basemesh (ml/models/m09/mpfb_calibration.json, built by
measuring 242 generated bodies: mesh height and closed volume x 1.01 kg/L). No training: interpolation.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np

CALIBRATION = Path(__file__).resolve().parents[1] / "models" / "m09" / "mpfb_calibration.json"
SEX_TO_GENDER = {"female": 0.0, "male": 1.0}


MUSCLES = (0.0, 0.25, 0.5)  # grid values; heavy bodies in MakeHuman = high weight + low muscle


@lru_cache(maxsize=1)
def _grids() -> dict[float, tuple[np.ndarray, np.ndarray]]:
    """gender -> (H, M) arrays indexed [muscle, height, weight] on the calibration grid."""
    rows = json.load(open(CALIBRATION))["rows"]
    out = {}
    for g in sorted({r["gender"] for r in rows}):
        H = np.zeros((len(MUSCLES), 11, 11))
        M = np.zeros_like(H)
        for r in rows:
            if r["gender"] == g:
                k, i, j = MUSCLES.index(r["muscle"]), int(round(r["height"] * 10)), int(round(r["weight"] * 10))
                H[k, i, j], M[k, i, j] = r["height_cm"], r["mass_kg"]
        out[g] = (H, M)
    return out


def _interp(grid: np.ndarray, mu: np.ndarray, h: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Trilinear interpolation on [muscle 0..0.5, height 0..1, weight 0..1]."""
    z = np.clip(mu, 0, 0.5) / 0.25
    x, y = np.clip(h, 0, 1) * 10, np.clip(w, 0, 1) * 10
    k0, i0, j0 = np.minimum(z.astype(int), 1), np.minimum(x.astype(int), 9), np.minimum(y.astype(int), 9)
    fz, fx, fy = z - k0, x - i0, y - j0
    out = 0.0
    for dk, wk in ((0, 1 - fz), (1, fz)):
        for di, wi in ((0, 1 - fx), (1, fx)):
            for dj, wj in ((0, 1 - fy), (1, fy)):
                out = out + grid[k0 + dk, i0 + di, j0 + dj] * wk * wi * wj
    return out


def predict(sex: str, height: float, weight: float, muscle: float = 0.5) -> tuple[float, float]:
    """MPFB sliders -> (height_cm, mass_kg)."""
    H, M = _grids()[SEX_TO_GENDER[sex]]
    a = [np.array([v]) for v in (muscle, height, weight)]
    return float(_interp(H, *a)[0]), float(_interp(M, *a)[0])


def fit(sex: str, height_cm: float, weight_kg: float) -> dict:
    """(sex, cm, kg) -> MPFB {"gender", "height", "weight", "muscle"} + what the avatar will measure.
    Average muscle (0.5) is preferred; lower muscle is used only when the weight needs it."""
    H, M = _grids()[SEX_TO_GENDER[sex]]
    hs, ws, ms = np.linspace(0, 1, 201), np.linspace(0, 1, 201), np.linspace(0, 0.5, 21)
    mu, hh, ww = np.meshgrid(ms, hs, ws, indexing="ij")
    ph, pm = _interp(H, mu, hh, ww), _interp(M, mu, hh, ww)
    err = 4 * ((ph - height_cm) / height_cm) ** 2 + ((pm - weight_kg) / weight_kg) ** 2 + 0.002 * (mu - 0.5) ** 2
    k, i, j = np.unravel_index(np.argmin(err), err.shape)
    return {"gender": SEX_TO_GENDER[sex], "height": round(float(hs[i]), 4), "weight": round(float(ws[j]), 4),
            "muscle": round(float(ms[k]), 4), "avatar_height_cm": round(float(ph[k, i, j]), 1),
            "avatar_weight_kg": round(float(pm[k, i, j]), 1), "bmi": round(weight_kg / (height_cm / 100) ** 2, 1)}


if __name__ == "__main__":
    for case in [("male", 170, 70), ("female", 160, 55), ("male", 185, 95), ("female", 172, 80), ("male", 165, 58),
                 ("male", 178, 120), ("female", 155, 48)]:
        print(case, fit(*case))
