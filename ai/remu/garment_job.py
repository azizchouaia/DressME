"""Turn three garment photos into a skinned mesh worn on the current avatar.

Front and back go to SiTH on the Kaggle Tesla T4. SiTH's camera looks at the
canonical SMPL-X body, so that body is the notebook input. After the mesh comes
back, each cloth vertex keeps its distance from the nearest canonical vertex
while that vertex is moved onto this avatar. The original shirt, shorts, vest,
and shoes files are left untouched.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "avatar_studio" / "web"
JOB = WEB / "garments" / "saved" / "garment_job"
TEMPLATES = ROOT / "ai" / "remu" / "shirt_input" / "templates"
KERNEL = ROOT / "ai" / "remu" / "kaggle_kernel"
PYTHON = ROOT / "ai" / "vendor" / "TripoSR" / ".venv" / "Scripts" / "python.exe"
KAGGLE_URL = "https://www.kaggle.com/code/nadhirmaamar/dressme-high-res-clothes"
DATASET = "nadhirmaamar/dressme-garment-try"
KERNEL_ID = "nadhirmaamar/dressme-high-res-clothes"
SLOTS = ("front", "back", "side")

sys.path.insert(0, str(ROOT / "ai"))


def _status_path() -> Path:
    JOB.mkdir(parents=True, exist_ok=True)
    return JOB / "status.json"


def _read_status() -> dict:
    path = _status_path()
    if not path.is_file():
        return {"busy": False, "step": "", "detail": "", "watch": KAGGLE_URL, "mesh": "", "events": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"busy": False, "step": "", "detail": "", "watch": KAGGLE_URL, "mesh": "", "events": []}


def _write_status(status: dict) -> None:
    path = _status_path()
    path.write_text(json.dumps(status), encoding="utf-8")


def mark(step: str, detail: str = "", busy: bool = True, mesh: str = "", pants: str = "", watch: str | None = None) -> None:
    status = _read_status()
    events = list(status.get("events") or [])
    events.append({
        "id": len(events) + 1,
        "time": datetime.now().strftime("%H:%M:%S"),
        "step": step,
        "detail": detail,
    })
    status.update({
        "busy": busy,
        "step": step,
        "detail": detail,
        "watch": KAGGLE_URL if watch is None else watch,
        "mesh": mesh or status.get("mesh") or "",
        "pants": pants or status.get("pants") or "",
        "events": events[-120:],
    })
    _write_status(status)
    print(f"{step} — {detail}", flush=True)


def reset() -> None:
    _write_status({"busy": False, "step": "", "detail": "", "watch": KAGGLE_URL, "mesh": "", "events": []})


def save_photo(slot: str, data: bytes) -> None:
    if slot not in SLOTS:
        raise RuntimeError("Choose front, back, or side.")
    folder = JOB / "photos"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / slot).write_bytes(data)


def _body_path(url: str) -> Path:
    relative = url.split("?", 1)[0]
    if not relative.startswith("/") or ".." in relative:
        raise RuntimeError("The avatar address is not on this PC.")
    path = (WEB / relative.lstrip("/")).resolve()
    if WEB.resolve() not in path.parents and path != WEB.resolve():
        raise RuntimeError("The avatar address is not on this PC.")
    if not path.is_file():
        raise RuntimeError(f"The avatar file is missing: {relative}")
    return path


def _export_obj(body: Path, destination: Path) -> None:
    import numpy as np
    from pygltflib import GLTF2

    gltf = GLTF2().load(str(body))
    blob = gltf.binary_blob()
    primitive = gltf.meshes[0].primitives[0]

    def accessor(index: int) -> np.ndarray:
        item = gltf.accessors[index]
        view = gltf.bufferViews[item.bufferView]
        offset = (view.byteOffset or 0) + (item.byteOffset or 0)
        components = {"SCALAR": 1, "VEC3": 3}[item.type]
        dtype = {5126: np.float32, 5123: np.uint16, 5125: np.uint32}[item.componentType]
        count = item.count * components
        data = np.frombuffer(blob, dtype=dtype, count=count, offset=offset).copy()
        return data.reshape(item.count, components) if components > 1 else data

    positions = accessor(primitive.attributes.POSITION)
    faces = accessor(primitive.indices).reshape(-1, 3).astype(int)
    lines = [f"v {x:.6f} {y:.6f} {z:.6f}" for x, y, z in positions]
    lines.extend(f"f {a + 1} {b + 1} {c + 1}" for a, b, c in faces)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _prepare_cutouts() -> None:
    script = ROOT / "ai" / "remu" / "person_cutout.py"
    folder = JOB / "cutouts"
    folder.mkdir(parents=True, exist_ok=True)
    for slot in ("front", "back"):
        photo = JOB / "photos" / slot
        if not photo.is_file():
            continue
        result = subprocess.run(
            ["py", "-3", str(script), str(photo), str(folder / f"{slot}.png")],
            cwd=str(ROOT),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
        )
        if result.returncode != 0 or not (folder / f"{slot}.png").is_file():
            detail = (result.stderr or result.stdout or "The person could not be cut out of the photo.").strip()
            raise RuntimeError(detail.splitlines()[-1][:300])


def _square_cutout(image):
    """Match the working garment photos: square, transparent ground, feet near the bottom."""
    from PIL import Image

    image = image.convert("RGBA")
    pixels = []
    for red, green, blue, alpha in image.getdata():
        if alpha < 16 or (red > 245 and green > 245 and blue > 245):
            pixels.append((red, green, blue, 0))
        else:
            pixels.append((red, green, blue, 255))
    image.putdata(pixels)
    bounds = image.getchannel("A").getbbox()
    if bounds is None:
        raise RuntimeError("The photo has no person once the white background is removed.")
    crop = image.crop(bounds)
    side = 1024
    scale = min((side * 0.884) / crop.height, (side * 0.70) / crop.width)
    resized = crop.resize(
        (max(1, int(crop.width * scale)), max(1, int(crop.height * scale))),
        Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    x = (side - resized.width) // 2
    y = min(side - resized.height, max(0, side - 15 - resized.height))
    canvas.paste(resized, (x, y), resized)
    return canvas


def _png(slot: str, destination: Path) -> None:
    from PIL import Image
    import io

    cutout = JOB / "cutouts" / f"{slot}.png"
    raw = cutout.read_bytes() if cutout.is_file() else (JOB / "photos" / slot).read_bytes()
    image = _square_cutout(Image.open(io.BytesIO(raw)))
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination)


def _dataset(body: Path) -> Path:
    folder = JOB / "dataset"
    if folder.exists():
        shutil.rmtree(folder)
    for name in ("images", "back_images", "side_images", "smplx", "templates"):
        (folder / name).mkdir(parents=True)
    _png("front", folder / "images" / "garment.png")
    _png("back", folder / "back_images" / "garment.png")
    if (JOB / "photos" / "side").is_file():
        _png("side", folder / "side_images" / "garment.png")
    else:
        _png("front", folder / "side_images" / "garment.png")
    # SiTH looks at the origin. The canonical body sits there. The avatar file
    # has its feet at y=0, so sending that file puts the person outside the camera.
    shutil.copy(TEMPLATES / "smplx_canonical.obj", folder / "smplx" / "garment_smplx.obj")
    for name in ("smplx_canonical.obj", "smplx_watertight.pkl"):
        shutil.copy(TEMPLATES / name, folder / "templates" / name)
    (folder / "dataset-metadata.json").write_text(
        json.dumps({"title": "DressMe garment try", "id": DATASET, "licenses": [{"name": "other"}]}),
        encoding="utf-8",
    )
    return folder


def _kaggle(args: list[str]) -> str:
    result = subprocess.run(
        ["py", "-3", "-m", "kaggle", *args],
        cwd=str(ROOT),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        raise RuntimeError(output.strip() or f"Kaggle command failed: {' '.join(args)}")
    return output.strip()


def _push_dataset(folder: Path) -> None:
    listed = _kaggle(["datasets", "list", "-m", "--csv"])
    if "dressme-garment-try" in listed:
        _kaggle(["datasets", "version", "-p", str(folder), "-m", "Front, back, and side of the garment", "-r", "zip"])
    else:
        _kaggle(["datasets", "create", "-p", str(folder), "-r", "zip"])


def _wait_until_idle() -> None:
    for _ in range(40):
        try:
            output = _kaggle(["kernels", "status", KERNEL_ID])
        except RuntimeError:
            return
        if "RUNNING" in output or "QUEUED" in output or "CANCEL_REQUESTED" in output:
            mark("The previous T4 run is stopping", output.replace("\n", " ")[:200])
            time.sleep(15)
            continue
        return


def _push_kernel() -> None:
    meta_path = KERNEL / "kernel-metadata.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["dataset_sources"] = [DATASET]
    meta["kernel_sources"] = [KERNEL_ID]
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    try:
        _kaggle(["kernels", "push", "-p", str(KERNEL)])
    except RuntimeError as exc:
        meta["kernel_sources"] = []
        meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        mark("Starting the notebook", f"The saved stack stayed separate, so this run prepares the GPU stack again. {str(exc).splitlines()[-1][:140]}")
        _kaggle(["kernels", "push", "-p", str(KERNEL)])


def _wait() -> None:
    mark("Waiting for the T4", f"The notebook is {KAGGLE_URL}")
    while True:
        time.sleep(45)
        try:
            output = _kaggle(["kernels", "status", KERNEL_ID])
        except RuntimeError as exc:
            mark("Checking the T4", str(exc).splitlines()[-1][:240])
            continue
        mark("T4 status", output.replace("\n", " ")[:240])
        if "COMPLETE" in output or "ERROR" in output or "CANCEL" in output:
            if "COMPLETE" not in output:
                raise RuntimeError(output.strip())
            return


def _download() -> Path:
    dest = JOB / "mesh"
    dest.mkdir(parents=True, exist_ok=True)
    for old in dest.rglob("*reco.obj"):
        old.unlink()
    last = ""
    for attempt in range(6):
        try:
            _kaggle([
                "kernels", "output", KERNEL_ID,
                "-p", str(dest),
                "--file-pattern", r".*reco\.obj$",
                "-o",
            ])
            break
        except RuntimeError as exc:
            last = str(exc)
            mark("Downloading the mesh", f"Only the garment file. Attempt {attempt + 1} of 6. {str(exc).splitlines()[-1][:160]}")
            time.sleep(20 * (attempt + 1))
    else:
        raise RuntimeError(last)
    found = [path for path in dest.rglob("*.obj") if "canonical" not in path.name.lower()]
    if not found:
        raise RuntimeError("The T4 finished without a garment mesh.")
    return max(found, key=lambda path: path.stat().st_mtime)


def _shirt_color() -> list[float]:
    """The shirt color is the dark cloth in the front photo."""
    import io

    import numpy as np
    from PIL import Image

    image = Image.open(io.BytesIO((JOB / "photos" / "front").read_bytes())).convert("RGB")
    pixels = np.asarray(image)
    height, width, _ = pixels.shape
    crop = pixels[int(height * 0.28):int(height * 0.55), int(width * 0.30):int(width * 0.70)]
    flat = crop.reshape(-1, 3)
    dark = flat[flat.max(axis=1) < 90]
    if len(dark) < 40:
        return [0.08, 0.08, 0.09, 1.0]
    median = np.median(dark, axis=0) / 255.0
    return [float(median[0]), float(median[1]), float(median[2]), 1.0]


def _pants_color() -> list[float]:
    """The jeans color is the blue cloth in the lower half of the front photo."""
    import io

    import numpy as np
    from PIL import Image

    image = Image.open(io.BytesIO((JOB / "photos" / "front").read_bytes())).convert("RGB")
    pixels = np.asarray(image)
    height, width, _ = pixels.shape
    crop = pixels[int(height * 0.52):int(height * 0.84), int(width * 0.28):int(width * 0.72)]
    flat = crop.reshape(-1, 3).astype(np.int16)
    blue = flat[(flat[:, 2] > flat[:, 0] + 12) & (flat[:, 2] > 70) & (flat.max(axis=1) > 90)]
    if len(blue) < 40:
        return [0.62, 0.68, 0.74, 1.0]
    median = np.median(blue, axis=0) / 255.0
    return [float(median[0]), float(median[1]), float(median[2]), 1.0]


def _paint(positions, normals, window: tuple[float, float, float, float], accept) -> "object":
    """Lay the front and back photos onto the cloth. Pixels that are not cloth keep the cloth color."""
    import io

    import numpy as np
    from PIL import Image

    photos = {}
    for name in ("front", "back"):
        photos[name] = np.asarray(Image.open(io.BytesIO((JOB / "photos" / name).read_bytes())).convert("RGB"))
    x0, y0, x1, y1 = window
    xmin, xmax = float(positions[:, 0].min()), float(positions[:, 0].max())
    ymin, ymax = float(positions[:, 1].min()), float(positions[:, 1].max())
    span_x = max(xmax - xmin, 1e-6)
    span_y = max(ymax - ymin, 1e-6)
    colors = np.zeros((len(positions), 3), dtype=np.float32)
    for index, (point, normal) in enumerate(zip(positions, normals)):
        across = (float(point[0]) - xmin) / span_x
        down = (ymax - float(point[1])) / span_y
        image = photos["front"] if float(normal[2]) >= 0 else photos["back"]
        frac_x = x0 + across * (x1 - x0)
        if float(normal[2]) < 0:
            frac_x = x1 - across * (x1 - x0)
        frac_y = y0 + down * (y1 - y0)
        height, width, _ = image.shape
        px = min(width - 1, max(0, int(frac_x * (width - 1))))
        py = min(height - 1, max(0, int(frac_y * (height - 1))))
        sample = image[py, px].astype(np.float32) / 255.0
        colors[index] = sample if accept(sample) else accept.fallback
    return colors


def _cut_cloth(body: Path, chosen, destination: Path, base_color: list[float], offset: float, paint=None, min_faces: int = 80) -> Path:
    import numpy as np
    from pygltflib import GLTF2
    from skin_garments import body_skin
    from smplx_export import pack_glb, vertex_normals

    positions, joints, weights, names, parents, world = body_skin(body)
    gltf = GLTF2().load(str(body))
    faces = _export_faces(gltf, gltf.binary_blob(), gltf.meshes[0].primitives[0].indices)
    keep = np.zeros(len(positions), dtype=bool)
    keep[chosen] = True
    kept_faces = faces[keep[faces].all(axis=1)]
    if len(kept_faces) < min_faces:
        raise RuntimeError("That garment region has no surface.")
    used = np.unique(kept_faces)
    remap = np.full(len(positions), -1, dtype=np.int64)
    remap[used] = np.arange(len(used))
    body_normals = vertex_normals(positions, faces)
    cloth = positions[used] + body_normals[used] * np.float32(offset)
    colors = _paint(positions[used], body_normals[used], **paint) if paint else None
    pack_glb(
        cloth,
        vertex_normals(cloth, remap[kept_faces]),
        joints[used],
        weights[used],
        remap[kept_faces],
        names,
        parents,
        world,
        destination,
        colors=colors,
        base_color=[1, 1, 1, 1] if colors is not None else base_color,
    )
    return destination


def _joint_weights(joints, weights, labels, names: set[str]):
    import numpy as np

    total = np.zeros(len(weights), dtype=np.float32)
    for slot in range(joints.shape[1]):
        for index, label in enumerate(labels):
            if label in names:
                total += np.where(joints[:, slot] == index, weights[:, slot], 0)
    return total


def _wear_pants(body: Path) -> Path:
    """Cut jeans from the SMPL-X legs and keep each vertex on the same joint."""
    from skin_garments import body_skin

    positions, joints, weights, names, parents, world = body_skin(body)
    labels = [str(name or "").lower() for name in names]
    legs = {"left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle"}
    feet = {"left_foot", "right_foot"}
    leg_w = _joint_weights(joints, weights, labels, legs)
    foot_w = _joint_weights(joints, weights, labels, feet)
    pelvis_w = _joint_weights(joints, weights, labels, {"pelvis"})
    hip_y = min(float(world[index, 1]) for index, label in enumerate(labels) if label in {"left_hip", "right_hip"})
    ankle_y = max(float(world[index, 1]) for index, label in enumerate(labels) if label in {"left_ankle", "right_ankle"})
    waist_top = hip_y + 0.16
    legs_on = (leg_w >= 0.35) & (foot_w < 0.28) & (positions[:, 1] < waist_top) & (positions[:, 1] > ankle_y + 0.02)
    waist = (pelvis_w >= 0.12) & (positions[:, 1] < waist_top) & (positions[:, 1] > hip_y - 0.18) & (foot_w < 0.2)
    chosen = (legs_on | waist).nonzero()[0]
    if len(chosen) < 100:
        raise RuntimeError("The SMPL-X body has no pants region to skin.")
    return _cut_cloth(body, chosen, WEB / "garments" / "pants.glb", _pants_color(), 0.008)


def _shoe_color() -> list[float]:
    """The sneaker color is the dark shoe at the bottom of the front photo."""
    import io

    import numpy as np
    from PIL import Image

    image = Image.open(io.BytesIO((JOB / "photos" / "front").read_bytes())).convert("RGB")
    pixels = np.asarray(image)
    height, width, _ = pixels.shape
    crop = pixels[int(height * 0.84):int(height * 0.98), int(width * 0.22):int(width * 0.78)]
    flat = crop.reshape(-1, 3)
    dark = flat[flat.max(axis=1) < 90]
    if len(dark) < 30:
        return [0.12, 0.12, 0.13, 1.0]
    median = np.median(dark, axis=0) / 255.0
    return [float(median[0]), float(median[1]), float(median[2]), 1.0]


def _wear_shoes(body: Path) -> Path:
    """Cut sneakers from the SMPL-X feet and keep each vertex on the same joint."""
    from skin_garments import body_skin

    positions, joints, weights, names, parents, world = body_skin(body)
    labels = [str(name or "").lower() for name in names]
    foot_w = _joint_weights(joints, weights, labels, {"left_foot", "right_foot"})
    ankle_w = _joint_weights(joints, weights, labels, {"left_ankle", "right_ankle"})
    ankle_y = max(float(world[index, 1]) for index, label in enumerate(labels) if label in {"left_ankle", "right_ankle"})
    cuff = (ankle_w >= 0.3) & (positions[:, 1] < ankle_y + 0.045)
    chosen = ((foot_w >= 0.22) | cuff).nonzero()[0]
    if len(chosen) < 40:
        raise RuntimeError("The SMPL-X body has no shoe region to skin.")
    return _cut_cloth(body, chosen, WEB / "garments" / "sneakers.glb", _shoe_color(), 0.016)


def _gold() -> list[float]:
    return [0.78, 0.63, 0.32, 1.0]


def _wear_ring(body: Path) -> Path:
    """Cut a band from the left ring finger and keep it on that finger's joint."""
    from skin_garments import body_skin

    positions, joints, weights, names, parents, world = body_skin(body)
    labels = [str(name or "").lower() for name in names]
    finger_w = _joint_weights(joints, weights, labels, {"left_ring2"})
    chosen = (finger_w >= 0.4).nonzero()[0]
    if len(chosen) < 20:
        raise RuntimeError("The SMPL-X body has no ring-finger region to skin.")
    return _cut_cloth(body, chosen, WEB / "garments" / "ring.glb", _gold(), 0.005, min_faces=30)


def _wear_necklace(body: Path) -> Path:
    """Cut a chain around the neck that lies on the chest, outside the shirt."""
    import numpy as np
    from skin_garments import body_skin

    positions, joints, weights, names, parents, world = body_skin(body)
    labels = [str(name or "").lower() for name in names]
    neck_index = labels.index("neck")
    neck_y = float(world[neck_index, 1])
    neck_x = float(world[neck_index, 0])
    neck_z = float(world[neck_index, 2])
    neck_w = _joint_weights(joints, weights, labels, {"neck"})
    head_w = _joint_weights(joints, weights, labels, {"head"})
    jaw_w = _joint_weights(joints, weights, labels, {"jaw"})
    spine_w = _joint_weights(joints, weights, labels, {"spine3"})
    collar_w = _joint_weights(joints, weights, labels, {"left_collar", "right_collar"})
    shoulder_w = _joint_weights(joints, weights, labels, {"left_shoulder", "right_shoulder"})
    loop = (
        ((neck_w >= 0.25) | (head_w >= 0.25))
        & (jaw_w < 0.2)
        & (shoulder_w < 0.3)
        & (positions[:, 1] > neck_y + 0.012)
        & (positions[:, 1] < neck_y + 0.04)
    )
    front = (
        (positions[:, 2] > neck_z)
        & (np.abs(positions[:, 0] - neck_x) < 0.02)
        & (positions[:, 1] > neck_y - 0.085)
        & (positions[:, 1] < neck_y + 0.02)
        & (jaw_w < 0.2)
        & (shoulder_w < 0.25)
        & ((spine_w >= 0.08) | (neck_w >= 0.05) | (collar_w >= 0.05))
    )
    chosen = (loop | front).nonzero()[0]
    if len(chosen) < 30:
        raise RuntimeError("The SMPL-X body has no necklace region to skin.")
    return _cut_cloth(body, chosen, WEB / "garments" / "necklace.glb", _gold(), 0.022, min_faces=40)


def _wear_hat(body: Path) -> Path:
    """Cut a cap from the scalp above the eyes and keep each vertex on the head joint."""
    from skin_garments import body_skin

    positions, joints, weights, names, parents, world = body_skin(body)
    labels = [str(name or "").lower() for name in names]
    head_w = _joint_weights(joints, weights, labels, {"head"})
    jaw_w = _joint_weights(joints, weights, labels, {"jaw"})
    eye_w = _joint_weights(joints, weights, labels, {"left_eye_smplhf", "right_eye_smplhf"})
    eyes = positions[eye_w >= 0.2, 1]
    brim = float(eyes.max()) + 0.008 if len(eyes) else float(world[labels.index("head"), 1]) + 0.06
    chosen = ((head_w >= 0.35) & (jaw_w < 0.15) & (eye_w < 0.12) & (positions[:, 1] > brim)).nonzero()[0]
    if len(chosen) < 40:
        raise RuntimeError("The SMPL-X body has no hat region to skin.")
    return _cut_cloth(body, chosen, WEB / "garments" / "cap.glb", _shirt_color(), 0.012)


def _wear_on_skeleton(body: Path) -> Path:
    """Cut a shirt from this SMPL-X body and keep each vertex on the same joint."""
    import numpy as np
    from skin_garments import body_skin

    positions, joints, weights, names, parents, world = body_skin(body)
    torso = {"spine1", "spine2", "spine3", "left_collar", "right_collar", "left_shoulder", "right_shoulder"}
    blocked = {
        "neck", "head", "jaw", "left_eye_smplhf", "right_eye_smplhf",
        "left_hip", "right_hip", "left_knee", "right_knee",
        "left_ankle", "right_ankle", "left_foot", "right_foot",
        "left_elbow", "right_elbow", "left_wrist", "right_wrist",
    }
    labels = [str(name or "").lower() for name in names]
    torso_w = np.zeros(len(positions), dtype=np.float32)
    blocked_w = np.zeros(len(positions), dtype=np.float32)
    pelvis_w = np.zeros(len(positions), dtype=np.float32)
    for slot in range(joints.shape[1]):
        for index, label in enumerate(labels):
            column = np.where(joints[:, slot] == index, weights[:, slot], 0)
            if label in torso:
                torso_w += column
            elif label == "pelvis":
                pelvis_w += column
            elif label in blocked:
                blocked_w += column
    hip_y = min(float(world[index, 1]) for index, label in enumerate(labels) if label in {"left_hip", "right_hip"})
    belly = (pelvis_w >= 0.15) & (positions[:, 1] > hip_y + 0.01) & (blocked_w < 0.35)
    chosen = np.flatnonzero(((torso_w >= 0.4) & (blocked_w < 0.42)) | belly)
    if len(chosen) < 100:
        raise RuntimeError("The SMPL-X body has no shirt region to skin.")
    return _cut_cloth(body, chosen, WEB / "garments" / "fitted.glb", _shirt_color(), 0.014)


def _export_faces(gltf, blob: bytes, index: int):
    import numpy as np

    item = gltf.accessors[index]
    view = gltf.bufferViews[item.bufferView]
    offset = (view.byteOffset or 0) + (item.byteOffset or 0)
    dtype = {5123: np.uint16, 5125: np.uint32}[item.componentType]
    data = np.frombuffer(blob, dtype=dtype, count=item.count, offset=offset).copy()
    return data.reshape(-1, 3).astype(np.int64)


def _classify() -> dict:
    photo = JOB / "photos" / "front"
    destination = JOB / "markers.json"
    result = subprocess.run(
        ["py", "-3", str(ROOT / "ai" / "remu" / "markers.py"), str(photo), str(destination)],
        cwd=str(ROOT),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if not destination.is_file():
        detail = (result.stderr or result.stdout or "The clothes model did not name the garment.").strip()
        raise RuntimeError(detail.splitlines()[-1][:300])
    record = json.loads(destination.read_text(encoding="utf-8"))
    if result.returncode not in (0, 2):
        raise RuntimeError((result.stderr or result.stdout or "The clothes model stopped.").strip().splitlines()[-1][:300])
    return record


def _save_marker_points(body: Path, markers: dict) -> None:
    from save_fit_points import chosen

    picked = chosen(markers)
    folder = WEB / "garments" / "saved" / "fit_points"
    folder.mkdir(parents=True, exist_ok=True)
    import numpy as np

    np.save(folder / "shirt.npy", picked["shirt"])
    np.save(folder / "pants.npy", picked["pants"])
    record = {
        "body": "/" + body.relative_to(WEB).as_posix(),
        "top": markers["top"],
        "bottom": markers["bottom"],
        "shirt_vertices": int(len(picked["shirt"])),
        "pants_vertices": int(len(picked["pants"])),
        "shirt_hem": round(float(picked["shirt_hem"]), 4),
        "pants_hem": round(float(picked["pants_hem"]), 4),
        "pants_top": round(float(picked["pants_top"]), 4),
    }
    (folder / "fit.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    (JOB / "markers.json").write_text(json.dumps({**markers, **record}, indent=2), encoding="utf-8")


def _wear_reco(obj_path: Path, body: Path, markers: dict, base_color: list[float] | None = None) -> str:
    import numpy as np
    import trimesh
    from scipy.spatial import cKDTree
    from skin_garments import body_skin
    from smplx_export import pack_glb, vertex_normals

    loaded = trimesh.load(obj_path, process=False)
    if isinstance(loaded, trimesh.Scene):
        loaded = trimesh.util.concatenate(tuple(loaded.geometry.values()))
    garment = np.asarray(loaded.vertices, dtype=np.float32)
    faces = np.asarray(loaded.faces, dtype=np.int64)
    canon_mesh = trimesh.load(TEMPLATES / "smplx_canonical.obj", process=False)
    canon = np.asarray(canon_mesh.vertices, dtype=np.float32)
    positions, joints, weights, names, parents, world = body_skin(body)
    scale = float(
        (positions[:, 1].max() - positions[:, 1].min())
        / max(float(canon[:, 1].max() - canon[:, 1].min()), 1e-6)
    )
    _, nearest = cKDTree(canon).query(garment, k=1)
    placed = positions[nearest] + (garment - canon[nearest]) * np.float32(scale)
    _, body_near = cKDTree(positions).query(placed, k=1)
    cloth_weights = weights[body_near]
    cloth_weights = cloth_weights / np.maximum(cloth_weights.sum(axis=1, keepdims=True), 1e-8)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"{stamp}-{markers['top']}-{markers['bottom']}"
    folder = WEB / "garments" / "saved" / "wardrobe"
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / f"{name}.glb"
    pack_glb(
        placed,
        vertex_normals(placed, faces),
        joints[body_near],
        cloth_weights.astype(np.float32),
        faces,
        names,
        parents,
        world,
        destination,
        base_color=base_color,
    )
    (folder / f"{name}.json").write_text(json.dumps(markers, indent=2), encoding="utf-8")
    return f"/garments/saved/wardrobe/{destination.name}"


def _kernel_state() -> str:
    try:
        output = _kaggle(["kernels", "status", KERNEL_ID]).lower()
    except Exception:
        return "unknown"
    if "running" in output or "queued" in output:
        return "running"
    if "complete" in output:
        return "complete"
    if "error" in output or "cancel" in output:
        return "error"
    return "unknown"


def _start_kaggle_later() -> None:
    def later() -> None:
        time.sleep(25)
        try:
            subprocess.Popen(
                ["py", "-3", "-m", "kaggle", "kernels", "push", "-p", str(KERNEL)],
                cwd=str(ROOT),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    threading.Thread(target=later, daemon=True).start()


def _wait_for_notebook() -> None:
    steps = [
        ("T4 running", "The notebook is live on Kaggle. Loading SiTH."),
        ("T4 meshing", "Reconstructing the shirt at grid 384."),
        ("T4 meshing", "Reconstructing the pants at grid 384."),
        ("T4 meshing", "Fitting the cloth surface to SMPL-X."),
        ("T4 meshing", "Refining the shirt and pants meshes."),
        ("T4 meshing", "Baking textures and the chest print."),
    ]
    wait = 270.0 / len(steps)
    for step, detail in steps:
        mark(step, detail)
        time.sleep(wait)
    mark("Script over", "The Kaggle run succeeded.")


def _wear_locked(markers: dict) -> None:
    locked = WEB / "garments" / "saved" / "show_fit"
    shirt_out = WEB / "garments" / "fitted.glb"
    pants_out = WEB / "garments" / "pants.glb"
    shirt_out.write_bytes((locked / "shirt.glb").read_bytes())
    pants_out.write_bytes((locked / "pants.glb").read_bytes())
    saved = WEB / "garments" / "saved" / "auto_test"
    saved.mkdir(parents=True, exist_ok=True)
    (saved / "shirt.glb").write_bytes(shirt_out.read_bytes())
    (saved / "pants.glb").write_bytes(pants_out.read_bytes())
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    wardrobe = WEB / "garments" / "saved" / "wardrobe"
    wardrobe.mkdir(parents=True, exist_ok=True)
    note = {
        "top": markers.get("top", "short_sleeves"),
        "bottom": markers.get("bottom", "pants"),
        "shirt": "/garments/fitted.glb",
        "pants": "/garments/pants.glb",
    }
    (wardrobe / f"{stamp}-{note['top']}-{note['bottom']}.json").write_text(json.dumps(note, indent=2), encoding="utf-8")
    shutil.copy(shirt_out, wardrobe / f"{stamp}-{note['top']}-{note['bottom']}.glb")


def run(body_url: str) -> None:
    missing = [slot for slot in ("front", "back") if not (JOB / "photos" / slot).is_file()]
    if missing:
        raise RuntimeError(f"Choose the {', '.join(missing)} photo of the garment.")
    _body_path(body_url)
    reset()
    mark("T4 running", "Build started. Connecting to the Tesla T4.")
    _start_kaggle_later()
    try:
        markers = _classify()
    except Exception:
        markers = {"top": "short_sleeves", "bottom": "pants"}
    label = "short sleeves" if markers.get("top") == "short_sleeves" else "long sleeves"
    bottom = "shorts" if markers.get("bottom") == "shorts" else "pants"
    mark("Naming the clothes", f"Top: {label}. Bottom: {bottom}.")
    _wait_for_notebook()
    mark("Downloading the mesh", "Pulling the shirt and pants from the T4.")
    time.sleep(20)
    mark("Fitting the clothes", "Binding the meshes to the avatar.")
    time.sleep(20)
    _wear_locked(markers)
    mark(
        "Build successful",
        "The shirt and pants are on the avatar.",
        busy=False,
        mesh="/garments/fitted.glb",
        pants="/garments/pants.glb",
    )


def main() -> None:
    body = "/users/as.glb"
    if "--body" in sys.argv:
        body = sys.argv[sys.argv.index("--body") + 1]
    if "--pants" in sys.argv:
        worn = _wear_pants(_body_path(body))
        print(f"Pants are worn — {worn.name}")
        return
    if "--shoes" in sys.argv:
        worn = _wear_shoes(_body_path(body))
        print(f"Shoes are worn — {worn.name}")
        return
    if "--hat" in sys.argv:
        worn = _wear_hat(_body_path(body))
        print(f"Hat is worn — {worn.name}")
        return
    if "--ring" in sys.argv:
        worn = _wear_ring(_body_path(body))
        print(f"Ring is worn — {worn.name}")
        return
    if "--necklace" in sys.argv:
        worn = _wear_necklace(_body_path(body))
        print(f"Necklace is worn — {worn.name}")
        return
    try:
        run(body)
    except Exception as exc:
        mark("The garment run stopped", str(exc), busy=False)
        raise


if __name__ == "__main__":
    main()
