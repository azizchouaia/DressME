"""Owner: BO7 · puts the picked pieces on BO9's 3D garments, for the "share a look on my avatar" card.

BO9 (viewer-bo9) dresses its SMPL-X body with three skinned garments: a shirt, shorts and a vest, made for
the `smplx_thin` body (same coordinates as the body, metres, feet at y = 0). BO9's files are not changed: this
module builds, for one request, a copy of a garment GLB that matches the piece of the user's wardrobe (M1):

  shape     the template is reshaped by simple rules (if/else on the piece's category and name):
              top       short sleeves for t-shirts / polos / tops; long for shirts, hoodies, jackets
              bottom    trousers / serwal / jeans to the ankle, skirts to the knee and wider, shorts as is
              one-piece dress to the knee; jebba / kachabia / sefsari / blouza to the ankle (shirt lengthened)
  texture   the piece's own photo (M1 cutout), projected from the front onto the garment (planar UV mapping),
            its background replaced by the piece's colour; without a photo, BO9's texture tinted.

Only POSITION and TEXCOORD_0 values are rewritten in place (same sizes) and a new PNG is appended, so the skin
(joints, weights) stays BO9's and the garment still follows the body's pose.
"""

import io
import json
import struct

import numpy as np
from PIL import Image, ImageOps

ANKLE_Y, KNEE_Y = 0.10, 0.46  # smplx_thin body (1.70 m)
SHORT_SLEEVE_X = 0.40  # |x| where a short sleeve ends (T-pose)
LONG_BOTTOM = ("trouser", "serwal", "jean", "pant", "legging", "jogger", "sarouel")
SKIRT = ("skirt", "jupe")
SHORT_TOP = ("t-shirt", "tshirt", "polo", "tank", "top", "blouse", "blouza", "dress")
LONG_SLEEVE = (
    "long-sleeve",
    "long sleeve",
    "hoodie",
    "sweat",
    "jacket",
    "blazer",
    "coat",
    "jebba",
    "kachabia",
)
ANKLE_ONE_PIECE = ("jebba", "kachabia", "sefsari", "blouza", "abaya", "kaftan", "caftan", "maxi")


def shape_for(garment: str, category: str, name: str) -> str:
    """if/else rules: which form of BO9's template fits this piece."""
    n = (name or "").lower()
    if garment == "shorts":
        if any(w in n for w in LONG_BOTTOM):
            return "trousers"
        return "skirt" if any(w in n for w in SKIRT) else "shorts"
    if category in ("dress", "traditional"):
        return "ankle_dress" if any(w in n for w in ANKLE_ONE_PIECE) else "dress"
    if any(w in n for w in LONG_SLEEVE):
        return "long_top"
    return "short_top" if any(w in n for w in SHORT_TOP) else "long_top"


def _reshape(pos: np.ndarray, shape: str) -> np.ndarray:
    p = pos.copy()
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    if shape == "short_top":
        far = np.abs(x) > SHORT_SLEEVE_X  # sleeve beyond the elbow: folded back to a short sleeve
        x[far] = np.sign(x[far]) * SHORT_SLEEVE_X
    if shape in ("trousers", "skirt"):
        crotch, hem = 0.80, float(y.min())
        target = ANKLE_Y if shape == "trousers" else KNEE_Y
        low = y < crotch
        t = (crotch - y[low]) / max(crotch - hem, 1e-6)  # 0 at the crotch, 1 at the hem
        y[low] = crotch - t * (crotch - target)
        if shape == "skirt":  # one wider cone instead of two legs
            x[low] = x[low] * (1 + 0.9 * t) + np.sign(x[low]) * 0.05 * t
            z[low] = z[low] * (1 + 0.5 * t)
    if shape in ("dress", "ankle_dress"):
        waist, hem = 1.02, float(y.min())
        target = ANKLE_Y if shape == "ankle_dress" else KNEE_Y
        low = (y < waist) & (np.abs(x) < 0.30)  # the body of the shirt, not the sleeves
        t = (waist - y[low]) / max(waist - hem, 1e-6)
        y[low] = waist - t * (waist - target)
        x[low] = x[low] * (1 + 0.55 * t)  # flared, so the hem clears the legs
        z[low] = z[low] * (1 + 0.35 * t)
        if shape == "dress":
            far = np.abs(x) > SHORT_SLEEVE_X
            x[far] = np.sign(x[far]) * SHORT_SLEEVE_X
    return p


def _photo_texture(photo: Image.Image, rgb: tuple[int, int, int], size: int = 1024) -> Image.Image:
    """The piece cut from its background (alpha, or what differs from the corners), on its own colour."""
    img = photo.convert("RGBA")
    a = np.asarray(img).astype(np.int16)
    if (a[:, :, 3] < 250).mean() > 0.02:  # a real cutout
        mask = a[:, :, 3] > 40
    else:
        corners = np.concatenate([a[:8, :8, :3].reshape(-1, 3), a[-8:, -8:, :3].reshape(-1, 3)])
        bg = np.median(corners, axis=0)
        mask = np.abs(a[:, :, :3] - bg).sum(axis=2) > 60
    ys, xs = np.nonzero(mask)
    if len(xs) < 50:
        return Image.new("RGB", (size, size), rgb)
    box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    piece = img.crop(box)
    m = Image.fromarray((mask[box[1] : box[3], box[0] : box[2]] * 255).astype(np.uint8))
    out = Image.new("RGB", piece.size, rgb)
    out.paste(piece.convert("RGB"), (0, 0), m)
    return out.resize((size, size), Image.LANCZOS)


def _tinted(texture: Image.Image, rgb: tuple[int, int, int]) -> Image.Image:
    gray = ImageOps.autocontrast(texture.convert("L"), cutoff=2)
    shade = gray.point(lambda v: int(150 + v * 105 / 255))  # 0.59..1.0: folds stay visible
    return Image.merge("RGB", [shade.point(lambda v, c=c: v * c // 255) for c in rgb])


def dress_glb(
    glb: bytes,
    *,
    rgb: tuple[int, int, int] | None = None,
    photo: Image.Image | None = None,
    shape: str | None = None,
) -> bytes:
    """A copy of BO9's garment GLB, reshaped (`shape`) and textured with the piece's photo or colour."""
    magic, version, _ = struct.unpack_from("<III", glb, 0)
    if magic != 0x46546C67:  # "glTF"
        return glb
    jlen = struct.unpack_from("<I", glb, 12)[0]
    gltf = json.loads(glb[20 : 20 + jlen])
    blen = struct.unpack_from("<I", glb, 20 + jlen)[0]
    binary = bytearray(glb[28 + jlen : 28 + jlen + blen])

    def view_of(accessor: int) -> tuple[int, int, dict]:
        acc = gltf["accessors"][accessor]
        view = gltf["bufferViews"][acc["bufferView"]]
        return view.get("byteOffset", 0) + acc.get("byteOffset", 0), acc["count"], acc

    attrs, pos = {}, None
    if gltf.get("meshes"):
        attrs = gltf["meshes"][0]["primitives"][0]["attributes"]
        pos_off, count, pos_acc = view_of(attrs["POSITION"])
        pos = np.frombuffer(bytes(binary[pos_off : pos_off + count * 12]), dtype="<f4").reshape(count, 3)
        if shape and shape not in ("shorts",):
            pos = _reshape(pos, shape).astype("<f4")
            binary[pos_off : pos_off + count * 12] = pos.tobytes()
            pos_acc["min"] = [float(v) for v in pos.min(axis=0)]
            pos_acc["max"] = [float(v) for v in pos.max(axis=0)]
    try:
        tex_i = gltf["materials"][0]["pbrMetallicRoughness"]["baseColorTexture"]["index"]
        image = gltf["images"][gltf["textures"][tex_i]["source"]]
        img_view = gltf["bufferViews"][image["bufferView"]]
    except (KeyError, IndexError):
        return glb

    color = rgb or (200, 200, 200)
    if photo is not None and pos is not None and "TEXCOORD_0" in attrs:
        uv_off, uv_count, _ = view_of(attrs["TEXCOORD_0"])
        lo, hi = pos.min(axis=0), pos.max(axis=0)
        u = (pos[:, 0] - lo[0]) / max(hi[0] - lo[0], 1e-6)
        v = (hi[1] - pos[:, 1]) / max(hi[1] - lo[1], 1e-6)  # glTF: v = 0 at the top of the picture
        uv = np.stack([u, v], axis=1).astype("<f4")
        binary[uv_off : uv_off + uv_count * 8] = uv.tobytes()
        texture = _photo_texture(photo, color)
    elif rgb is not None:
        start = img_view.get("byteOffset", 0)
        texture = _tinted(Image.open(io.BytesIO(bytes(binary[start : start + img_view["byteLength"]]))), rgb)
    else:
        texture = None

    if texture is not None:
        buf = io.BytesIO()
        texture.save(buf, format="PNG")
        png = buf.getvalue()
        img_view["byteOffset"] = len(binary)  # the new picture goes at the end of the binary chunk
        img_view["byteLength"] = len(png)
        image["mimeType"] = "image/png"
        binary += png
        binary += b"\0" * (-len(binary) % 4)
    gltf["buffers"][0]["byteLength"] = len(binary)
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    total = 12 + 8 + len(js) + 8 + len(binary)
    return (
        struct.pack("<III", magic, version, total)
        + struct.pack("<II", len(js), 0x4E4F534A)
        + js
        + struct.pack("<II", len(binary), 0x004E4942)
        + bytes(binary)
    )
