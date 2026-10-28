"""Shape an SMPL-X body from a scan and export a posed skeleton.

SMPL-X is a research model. Download it yourself from
https://smpl-x.is.tue.mpg.de/ and keep the files out of git.
Expected file: ai/models/smplx/SMPLX_NEUTRAL.npz
Optional: SMPLX_FEMALE.npz and SMPLX_MALE.npz
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import torch
import trimesh
from pygltflib import (
    ARRAY_BUFFER,
    ELEMENT_ARRAY_BUFFER,
    FLOAT,
    UNSIGNED_INT,
    UNSIGNED_SHORT,
    Accessor,
    Asset,
    Attributes,
    Buffer,
    BufferView,
    GLTF2,
    Material,
    Mesh,
    Node,
    PbrMetallicRoughness,
    Primitive,
    Scene,
    Skin,
)
from smplx.joint_names import SMPLH_JOINT_NAMES

REPO = Path(__file__).resolve().parents[1]
MODEL_DIR = REPO / "ai" / "models" / "smplx"
DEFAULT_SCAN = REPO / "avatar_studio" / "web" / "avatar_ready.glb"
DEFAULT_OUT = REPO / "avatar_studio" / "web" / "smplx_body.glb"

JOINT_NAMES = (
    SMPLH_JOINT_NAMES[:22]
    + ["jaw", "left_eye_smplhf", "right_eye_smplhf"]
    + SMPLH_JOINT_NAMES[22:52]
)


def find_model(gender: str) -> Path | None:
    name = f"SMPLX_{gender.upper()}.npz"
    candidates = [
        MODEL_DIR / name,
        MODEL_DIR / "models" / "smplx" / name,
        MODEL_DIR / "smplx" / name,
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def missing_model_message() -> str:
    return (
        "SMPL-X is not on this machine yet.\n"
        "Download the research models from https://smpl-x.is.tue.mpg.de/\n"
        "(free registration, non-commercial research license).\n"
        "Copy SMPLX_NEUTRAL.npz to:\n"
        f"  {MODEL_DIR / 'SMPLX_NEUTRAL.npz'}\n"
        "Optional gendered files: SMPLX_FEMALE.npz and SMPLX_MALE.npz.\n"
        "Do not commit those files. Then run this script again."
    )


def measure_vertices(vertices: np.ndarray) -> dict[str, float]:
    """Torso widths, ignoring arms that stick out in a T-pose."""
    points = np.asarray(vertices, dtype=np.float64)
    y = points[:, 1]
    y0 = float(y.min())
    height = max(float(y.max() - y0), 1e-4)

    def half_width(low: float, high: float, axis: int) -> float:
        center = y0 + (low + high) * 0.5 * height
        width = max((high - low) * height, 1e-3)
        y_weight = np.exp(-((y - center) / width) ** 2)
        limit = 0.22 * height
        gate = 1.0 / (1.0 + np.exp(-(limit - np.abs(points[:, axis])) * 40.0))
        weight = y_weight * gate
        total = float(weight.sum())
        if total < 1e-4:
            return float(np.percentile(np.abs(points[:, axis]), 40))
        return float(np.sum(np.abs(points[:, axis]) * weight) / total)

    return {
        "height": height,
        "shoulder": half_width(0.72, 0.82, 0),
        "chest": half_width(0.66, 0.76, 0),
        "waist": half_width(0.56, 0.64, 0),
        "hip": half_width(0.46, 0.56, 0),
        "depth": half_width(0.62, 0.74, 2),
        "bust": _forward(points, y, y0, height, 0.66, 0.76),
        "thigh": _thigh_fraction(points, y, y0, height),
    }


def _forward(points: np.ndarray, y: np.ndarray, y0: float, height: float, low: float, high: float) -> float:
    center = y0 + (low + high) * 0.5 * height
    width = max((high - low) * height, 1e-3)
    weight = np.exp(-((y - center) / width) ** 2)
    weight *= 1.0 / (1.0 + np.exp(-points[:, 2] * 40.0))
    total = float(weight.sum())
    if total < 1e-4:
        return float(np.percentile(points[:, 2], 70))
    return float(np.sum(points[:, 2] * weight) / total)


def _thigh_fraction(points: np.ndarray, y: np.ndarray, y0: float, height: float) -> float:
    best_frac = 0.28
    best_radius = 1e9
    for step in range(8):
        frac = 0.22 + step * (0.20 / 7)
        center = y0 + frac * height
        band = np.abs(y - center) < 0.025 * height
        band &= np.abs(points[:, 0]) > 0.04 * height
        band &= np.abs(points[:, 0]) < 0.2 * height
        if int(band.sum()) < 20:
            continue
        radius = float(np.median(np.abs(points[band, 0])))
        if radius < best_radius:
            best_radius = radius
            best_frac = frac
    return float(np.clip(0.52 - best_frac, 0.16, 0.38))


def _mean(items: list[dict[str, float]], key: str) -> float | None:
    values = [item[key] for item in items if key in item]
    if not values:
        return None
    return float(np.mean(values))


def targets_from_labeled(views: list[tuple[str, np.ndarray]]) -> dict[str, float]:
    """Average each measurement from the photos that show it."""
    groups: dict[str, list[dict[str, float]]] = {"front": [], "back": [], "side": [], "three-quarter": []}
    for label, vertices in views:
        groups.setdefault(label, []).append(measure_vertices(vertices))
    front = groups["front"] or groups["three-quarter"]
    if not front:
        raise RuntimeError(
            "No photo looks like the front. Add a full-body photo facing the camera, arms straight out in a T-pose."
        )
    targets = {
        "height": _mean(front, "height"),
        "shoulder": _mean(front, "shoulder"),
        "hip": _mean(front, "hip"),
        "chest": _mean(front + groups["three-quarter"], "chest"),
        "waist": _mean(front, "waist"),
        "depth": _mean(front, "depth"),
        "bust": _mean(front + groups["three-quarter"], "bust"),
        "thigh": _mean(front, "thigh"),
    }
    if groups["back"]:
        targets["shoulder"] = (targets["shoulder"] + _mean(groups["back"], "shoulder")) / 2
        targets["hip"] = (targets["hip"] + _mean(groups["back"], "hip")) / 2
    if groups["side"]:
        targets["depth"] = _mean(groups["side"], "depth")
    return {key: value for key, value in targets.items() if value is not None}


def _forward_torch(vertices: torch.Tensor) -> torch.Tensor:
    y = vertices[:, 1]
    y0 = y.min()
    height = (y.max() - y0).clamp(min=1e-4)
    center = y0 + 0.71 * height
    width = (0.08 * height).clamp(min=1e-3)
    weight = torch.exp(-((y - center) / width) ** 2) * torch.sigmoid(vertices[:, 2] * 40)
    return (vertices[:, 2] * weight).sum() / weight.sum().clamp(min=1e-6)


def soft_band(vertices: torch.Tensor, low: float, high: float, axis: int) -> torch.Tensor:
    y = vertices[:, 1]
    y0 = y.min()
    height = (y.max() - y0).clamp(min=1e-4)
    center = y0 + (low + high) * 0.5 * height
    width = ((high - low) * height).clamp(min=1e-3)
    y_weight = torch.exp(-((y - center) / width) ** 2)
    limit = 0.22 * height
    gate = torch.sigmoid((limit - vertices[:, axis].abs()) * 40.0)
    weight = y_weight * gate
    return (vertices[:, axis].abs() * weight).sum() / weight.sum().clamp(min=1e-6)


def fit_betas(model, targets: dict[str, float]) -> torch.Tensor:
    betas = torch.zeros(1, 10, requires_grad=True)
    optimizer = torch.optim.Adam([betas], lr=0.08)
    zeros = {
        "body_pose": torch.zeros(1, 63),
        "left_hand_pose": torch.zeros(1, 45),
        "right_hand_pose": torch.zeros(1, 45),
        "expression": torch.zeros(1, 10),
        "jaw_pose": torch.zeros(1, 3),
    }
    for _ in range(60):
        optimizer.zero_grad()
        output = model(betas=betas, **zeros)
        vertices = output.vertices[0]
        joints = output.joints[0]
        height = vertices[:, 1].max() - vertices[:, 1].min()
        shoulder = soft_band(vertices, 0.72, 0.82, 0)
        chest = soft_band(vertices, 0.66, 0.76, 0)
        waist = soft_band(vertices, 0.56, 0.64, 0)
        hip = soft_band(vertices, 0.46, 0.56, 0)
        depth = soft_band(vertices, 0.66, 0.76, 2)
        bust = _forward_torch(vertices)
        thigh = ((joints[1, 1] - joints[4, 1]) + (joints[2, 1] - joints[5, 1])) * 0.5 / height.clamp(min=1e-4)
        loss = (betas ** 2).mean() * 0.04
        loss = loss + (height - targets["height"]) ** 2 * 6
        loss = loss + (shoulder - targets["shoulder"]) ** 2 * 8
        loss = loss + (hip - targets["hip"]) ** 2 * 8
        loss = loss + (depth - targets["depth"]) ** 2 * 6
        if "chest" in targets:
            loss = loss + (chest - targets["chest"]) ** 2 * 5
        if "waist" in targets:
            loss = loss + (waist - targets["waist"]) ** 2 * 5
        if "bust" in targets:
            loss = loss + (bust - targets["bust"]) ** 2 * 4
        if "thigh" in targets:
            loss = loss + (thigh - targets["thigh"]) ** 2 * 3
        loss.backward()
        optimizer.step()
        with torch.no_grad():
            betas.clamp_(-2, 2)
    return betas.detach()


def top_influences(weights: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    chosen = np.argpartition(-weights, 4, axis=1)[:, :4]
    rows = np.arange(weights.shape[0])[:, None]
    picked = weights[rows, chosen]
    order = np.argsort(-picked, axis=1)
    joints = np.take_along_axis(chosen, order, axis=1).astype(np.uint16)
    values = np.take_along_axis(picked, order, axis=1).astype(np.float32)
    values /= np.maximum(values.sum(axis=1, keepdims=True), 1e-8)
    return joints, values


def vertex_normals(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    normals = np.zeros_like(vertices, dtype=np.float64)
    triangles = vertices[faces]
    face_normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    np.add.at(normals, faces[:, 0], face_normals)
    np.add.at(normals, faces[:, 1], face_normals)
    np.add.at(normals, faces[:, 2], face_normals)
    length = np.linalg.norm(normals, axis=1, keepdims=True)
    return (normals / np.maximum(length, 1e-8)).astype(np.float32)


def pack_glb(vertices, normals, joints, weights, faces, names, parents, world_joints, destination: Path) -> None:
    blob = bytearray()
    views = []
    accessors = []

    def add_view(array: np.ndarray, target: int | None) -> int:
        raw = np.ascontiguousarray(array).tobytes()
        offset = len(blob)
        blob.extend(raw)
        blob.extend(b"\x00" * ((4 - (len(blob) % 4)) % 4))
        views.append(BufferView(buffer=0, byteOffset=offset, byteLength=len(raw), target=target))
        return len(views) - 1

    def add_accessor(array: np.ndarray, type_name: str, component: int, target: int | None) -> int:
        view = add_view(array, target)
        minimum = None
        maximum = None
        if array.ndim == 1 or (array.ndim == 2 and type_name in {"VEC3", "SCALAR"}):
            flat = array.reshape(array.shape[0], -1) if array.ndim > 1 else array.reshape(-1, 1)
            if type_name != "MAT4":
                minimum = flat.min(axis=0).astype(float).tolist()
                maximum = flat.max(axis=0).astype(float).tolist()
        accessors.append(
            Accessor(
                bufferView=view,
                componentType=component,
                count=array.shape[0],
                type=type_name,
                min=minimum,
                max=maximum,
            )
        )
        return len(accessors) - 1

    position_id = add_accessor(vertices.astype(np.float32), "VEC3", FLOAT, ARRAY_BUFFER)
    normal_id = add_accessor(normals.astype(np.float32), "VEC3", FLOAT, ARRAY_BUFFER)
    joint_id = add_accessor(joints.astype(np.uint16), "VEC4", UNSIGNED_SHORT, ARRAY_BUFFER)
    weight_id = add_accessor(weights.astype(np.float32), "VEC4", FLOAT, ARRAY_BUFFER)
    index_id = add_accessor(faces.astype(np.uint32).reshape(-1), "SCALAR", UNSIGNED_INT, ELEMENT_ARRAY_BUFFER)

    inverse = np.repeat(np.eye(4, dtype=np.float32)[None], len(world_joints), axis=0)
    inverse[:, :3, 3] = -world_joints.astype(np.float32)
    inverse_flat = np.ascontiguousarray(inverse.transpose(0, 2, 1)).reshape(len(world_joints), 16)
    inverse_id = add_accessor(inverse_flat.astype(np.float32), "MAT4", FLOAT, None)

    children: dict[int, list[int]] = {index: [] for index in range(len(names))}
    for index, parent in enumerate(parents):
        if parent >= 0:
            children[int(parent)].append(index)
    local = world_joints.copy()
    for index, parent in enumerate(parents):
        if parent >= 0:
            local[index] = world_joints[index] - world_joints[int(parent)]

    nodes = []
    for index, name in enumerate(names):
        nodes.append(
            Node(
                name=name,
                translation=local[index].astype(float).tolist(),
                children=children[index] or None,
            )
        )
    mesh_node = len(nodes)
    nodes.append(Node(name="SMPLX", mesh=0, skin=0))
    gltf = GLTF2(
        asset=Asset(version="2.0"),
        scene=0,
        scenes=[Scene(nodes=[mesh_node, 0])],
        nodes=nodes,
        skins=[Skin(name="SMPLX", joints=list(range(len(names))), inverseBindMatrices=inverse_id, skeleton=0)],
        meshes=[
            Mesh(
                primitives=[
                    Primitive(
                        attributes=Attributes(
                            POSITION=position_id,
                            NORMAL=normal_id,
                            JOINTS_0=joint_id,
                            WEIGHTS_0=weight_id,
                        ),
                        indices=index_id,
                        material=0,
                    )
                ]
            )
        ],
        materials=[
            Material(
                name="mannequin",
                pbrMetallicRoughness=PbrMetallicRoughness(
                    baseColorFactor=[0.847, 0.812, 0.776, 1],
                    metallicFactor=0.02,
                    roughnessFactor=0.58,
                ),
            )
        ],
        buffers=[Buffer(byteLength=len(blob))],
        bufferViews=views,
        accessors=accessors,
    )
    gltf.set_binary_blob(bytes(blob))
    destination.parent.mkdir(parents=True, exist_ok=True)
    gltf.save(destination)


_MODELS: dict[str, object] = {}


def load_body_model(gender: str):
    import smplx

    model_file = find_model(gender) or find_model("neutral")
    if model_file is None:
        raise SystemExit(missing_model_message())
    chosen = "female" if "FEMALE" in model_file.name else "male" if "MALE" in model_file.name else "neutral"
    if chosen == "neutral" and gender != "neutral":
        print(f"No {gender} SMPL-X file found. Using the neutral model.")
    cached = _MODELS.get(str(model_file))
    if cached is None:
        print(f"Loading {model_file.name}")
        cached = smplx.create(
            str(model_file),
            gender=chosen,
            use_pca=False,
            num_betas=10,
            flat_hand_mean=True,
            batch_size=1,
        )
        cached.eval()
        _MODELS[str(model_file)] = cached
    return cached, chosen


def export_body(scan: Path, destination: Path, gender: str, targets: dict[str, float] | None = None) -> str:
    if targets is None:
        if scan.is_file():
            mesh = trimesh.load(scan, force="mesh")
            targets = measure_vertices(np.asarray(mesh.vertices))
        else:
            targets = {"height": 1.75, "shoulder": 0.18, "hip": 0.16, "depth": 0.11}
    print(
        "Scan "
        f"height {targets['height']:.2f} m, "
        f"shoulders {targets['shoulder'] * 2:.2f} m, "
        f"hips {targets['hip'] * 2:.2f} m, "
        f"depth {targets['depth'] * 2:.2f} m"
    )
    model, chosen = load_body_model(gender)
    betas = fit_betas(model, targets)
    with torch.no_grad():
        output = model(
            betas=betas,
            body_pose=torch.zeros(1, 63),
            left_hand_pose=torch.zeros(1, 45),
            right_hand_pose=torch.zeros(1, 45),
            expression=torch.zeros(1, 10),
            jaw_pose=torch.zeros(1, 3),
        )
    vertices = output.vertices[0].cpu().numpy()
    current_height = float(vertices[:, 1].max() - vertices[:, 1].min())
    scale = float(np.clip(targets["height"] / max(current_height, 1e-4), 0.9, 1.1))
    vertices *= scale
    parents = model.parents.detach().cpu().numpy().astype(int)
    joint_count = len(parents)
    if joint_count != len(JOINT_NAMES):
        raise SystemExit(f"Expected {len(JOINT_NAMES)} joints, the model has {joint_count}.")
    joints = output.joints[0, :joint_count].cpu().numpy() * scale
    minimum_y = float(vertices[:, 1].min())
    center_x = float((vertices[:, 0].min() + vertices[:, 0].max()) / 2)
    center_z = float((vertices[:, 2].min() + vertices[:, 2].max()) / 2)
    shift = np.array([center_x, minimum_y, center_z])
    vertices = vertices - shift
    joints = joints - shift
    faces = np.asarray(model.faces, dtype=np.int64)
    skin_index, skin_weight = top_influences(model.lbs_weights.detach().cpu().numpy())
    pack_glb(
        vertices.astype(np.float32),
        vertex_normals(vertices, faces),
        skin_index,
        skin_weight,
        faces,
        JOINT_NAMES,
        parents,
        joints.astype(np.float32),
        destination,
    )
    print(f"Betas: {', '.join(f'{value:.2f}' for value in betas.flatten().tolist())}")
    print(f"Wrote {destination}")
    return chosen


def export_shaped(destination: Path, gender: str, betas: list[float], height: float = 1.7) -> tuple[str, float]:
    """Export one SMPL-X shape. Height is normalized so the presets differ in build, not stature."""
    values = list(betas) + [0.0] * 10
    beta = torch.tensor(values[:10], dtype=torch.float32).view(1, 10)
    model, chosen = load_body_model(gender)
    with torch.no_grad():
        output = model(
            betas=beta,
            body_pose=torch.zeros(1, 63),
            left_hand_pose=torch.zeros(1, 45),
            right_hand_pose=torch.zeros(1, 45),
            expression=torch.zeros(1, 10),
            jaw_pose=torch.zeros(1, 3),
        )
    vertices = output.vertices[0].cpu().numpy()
    current_height = float(vertices[:, 1].max() - vertices[:, 1].min())
    vertices *= height / max(current_height, 1e-4)
    parents = model.parents.detach().cpu().numpy().astype(int)
    joint_count = len(parents)
    if joint_count != len(JOINT_NAMES):
        raise SystemExit(f"Expected {len(JOINT_NAMES)} joints, the model has {joint_count}.")
    joints = output.joints[0, :joint_count].cpu().numpy() * (height / max(current_height, 1e-4))
    minimum_y = float(vertices[:, 1].min())
    center_x = float((vertices[:, 0].min() + vertices[:, 0].max()) / 2)
    center_z = float((vertices[:, 2].min() + vertices[:, 2].max()) / 2)
    shift = np.array([center_x, minimum_y, center_z])
    vertices = vertices - shift
    joints = joints - shift
    faces = np.asarray(model.faces, dtype=np.int64)
    skin_index, skin_weight = top_influences(model.lbs_weights.detach().cpu().numpy())
    pack_glb(
        vertices.astype(np.float32),
        vertex_normals(vertices, faces),
        skin_index,
        skin_weight,
        faces,
        JOINT_NAMES,
        parents,
        joints.astype(np.float32),
        destination,
    )
    hip = measure_vertices(vertices)["hip"]
    print(f"Wrote {destination.name}: hips {hip * 2:.2f} m")
    return chosen, hip


def write_presets(folder: Path) -> None:
    """Three builds, thin to heavy, for the female and male SMPL-X models."""
    folder.mkdir(parents=True, exist_ok=True)
    builds = {
        "thin": [-1.2, -2.0, 0.6],
        "average": [0.0],
        "heavy": [1.4, 2.2, -0.4],
    }
    for gender in ("female", "male"):
        for name, betas in builds.items():
            export_shaped(folder / f"{gender}_{name}.glb", gender, betas)
    print(f"Presets are in {folder}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fit SMPL-X shape to a scan and export a GLB.")
    parser.add_argument("--scan", type=Path, default=DEFAULT_SCAN)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--gender", choices=("neutral", "female", "male"), default="neutral")
    parser.add_argument("--presets", type=Path, default=None)
    args = parser.parse_args()
    if args.presets is not None:
        write_presets(args.presets)
        return
    export_body(args.scan, args.out, args.gender)


if __name__ == "__main__":
    sys.exit(main())
