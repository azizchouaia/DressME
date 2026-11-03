"""Keep the person and drop the room before a photo goes to ReMU."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

from vision_fit import _segment


def cut_person(source: Path, destination: Path) -> None:
    image, labels = _segment(source)
    person = labels != 0
    person = ndimage.binary_closing(person, iterations=2)
    person = ndimage.binary_fill_holes(person)
    if int(person.sum()) < 500:
        raise RuntimeError("The photo has no person to send to ReMU.")
    rgba = np.zeros((image.shape[0], image.shape[1], 4), dtype=np.uint8)
    rgba[..., :3] = image
    rgba[..., 3] = np.where(person, 255, 0).astype(np.uint8)
    destination.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba).save(destination)
    print("cut", destination.name, int(person.sum()))


def main() -> None:
    cut_person(Path(sys.argv[1]), Path(sys.argv[2]))


if __name__ == "__main__":
    main()
