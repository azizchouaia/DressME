"""ML · dominant colours of a garment cutout with K-means clustering (unsupervised learning).

Pixels of the cutout (alpha > 0, so the removed background is ignored) are clustered in RGB space;
the biggest cluster is the dominant colour. Used when an item comes with an image but no colour from M1,
and to report the colour palette of the card.
"""

import numpy as np
from PIL import Image
from sklearn.cluster import KMeans


def dominant_colors(
    img: Image.Image, k: int = 3, sample: int = 4000, seed: int = 0
) -> list[tuple[str, float]]:
    """Returns [(hex, share)] sorted by share, e.g. [("#E3CFAE", 0.71), ...]."""
    arr = np.asarray(img.convert("RGBA")).reshape(-1, 4)
    px = arr[arr[:, 3] > 128][:, :3].astype(float)
    if len(px) == 0:
        return []
    rng = np.random.default_rng(seed)
    if len(px) > sample:
        px = px[rng.choice(len(px), sample, replace=False)]
    k = min(k, len(np.unique(px, axis=0)))
    km = KMeans(n_clusters=k, n_init=4, random_state=seed).fit(px)
    counts = np.bincount(km.labels_, minlength=k)
    order = counts.argsort()[::-1]
    return [
        (
            "#{:02X}{:02X}{:02X}".format(*km.cluster_centers_[i].round().astype(int)),
            round(counts[i] / counts.sum(), 3),
        )
        for i in order
    ]
