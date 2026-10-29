"""Illustrations of the reference looks: a flat fashion figure wearing the look's real pieces and colours.

Each look describes its outfit in reference_looks.json (`art`): hair, skin, top, bottom or dress, outer layer,
shoes, bag. The figure is drawn on a 360 x 420 canvas, front view, in this order: hair (back), legs, bottom,
shoes, arms, top, outer layer, dress, bag, neck, head, hair (front). Without `art`, a plain figure in the
family colour is drawn. The card shows the title, so the picture has no text.

The look's vector stays the FashionCLIP vector of its description: FashionCLIP reads product photos, an
illustration would give an unreliable vector.
"""

from html import escape

OUTLINE = "#00000030"
DEFAULT_SKIN = "#E3B48F"
DEFAULT_HAIR = "#3B2A20"

# --- body (front view, centre x = 180) ---------------------------------------------------------------------
ARMS = ["M150 104 L138 108 L126 228 L138 230 L152 134 Z", "M210 104 L222 108 L234 228 L222 230 L208 134 Z"]
HANDS = [(132, 236), (228, 236)]
LEGS = ["M158 220 L176 220 L174 374 L162 374 Z", "M184 220 L202 220 L198 374 L186 374 Z"]
FEET = [168, 192]  # x of each shoe

# --- garments ----------------------------------------------------------------------------------------------
TOPS = {  # torso shapes: tucked (hem at the waist), untucked, oversized
    "tucked": "M148 102 L212 102 L206 150 L203 198 L157 198 L154 150 Z",
    "untucked": "M148 102 L212 102 L208 150 L209 216 L151 216 L152 150 Z",
    "oversized": "M141 100 L219 100 L223 150 L225 230 L135 230 L137 150 Z",
}
SLEEVES = {
    "long": [
        "M150 102 L136 106 L124 226 L140 228 L152 132 Z",
        "M210 102 L224 106 L236 226 L220 228 L208 132 Z",
    ],
    "wide": [
        "M146 100 L132 106 L118 226 L142 230 L152 134 Z",
        "M214 100 L228 106 L242 226 L218 230 L208 134 Z",
    ],
    "short": [
        "M150 102 L136 106 L131 142 L146 144 L152 122 Z",
        "M210 102 L224 106 L229 142 L214 144 L208 122 Z",
    ],
}
BOTTOMS = {
    "straight": "M157 194 L203 194 L211 226 L208 374 L184 374 L180 252 L176 374 L152 374 L149 226 Z",
    "slim": "M157 194 L203 194 L210 226 L204 370 L186 370 L180 252 L174 370 L156 370 L150 226 Z",
    "flare": "M157 194 L203 194 L210 226 L204 300 L216 374 L184 374 L180 254 L176 374 L144 374 L156 300 "
    "L150 226 Z",
    "wide": "M156 194 L204 194 L214 228 L215 374 L184 374 L180 254 L176 374 L145 374 L146 228 Z",
    "midi_skirt": "M157 194 L203 194 L224 318 L136 318 Z",
    "maxi_skirt": "M157 194 L203 194 L227 374 L133 374 Z",
}
DRESSES = {
    "maxi": "M150 102 L210 102 L206 150 L202 194 L228 374 L132 374 L158 194 L154 150 Z",
    "evening": "M156 114 L204 114 L204 150 L201 196 L216 340 L144 340 L159 196 L156 150 Z",
}


def _path(d: str, fill: str, extra: str = "") -> str:
    return (
        f'<path d="{d}" fill="{fill}" stroke="{OUTLINE}" stroke-width="1.5" stroke-linejoin="round"{extra}/>'
    )


def _line(d: str, colour: str, width: float = 1.5) -> str:
    return f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="{width}" stroke-linecap="round"/>'


def _mirror(d: str) -> str:
    """The same M / L / Z path on the other side of the figure (x -> 360 - x)."""
    out, is_x = [], True
    for tok in d.replace("M", " M ").replace("L", " L ").replace("Z", " Z ").split():
        if tok.isalpha():
            out.append(tok)
            is_x = True
        else:
            out.append(f"{360 - float(tok):g}" if is_x else tok)
            is_x = not is_x
    return " ".join(out)


def _pattern(pid: str, spec: dict) -> tuple[str, str]:
    """(defs, fill) of a garment: its colour, or an SVG pattern over it (dots, floral, sequins, lace)."""
    base, kind = spec.get("colour", "#C9C9C7"), spec.get("pattern")
    if not kind:
        return "", base
    accent = spec.get("pattern_colour", "#FFFFFF")
    size, motif = 14, ""
    if kind == "dots":
        motif = f'<circle cx="7" cy="7" r="2.6" fill="{accent}"/>'
    elif kind == "floral":
        size = 22
        leaf = spec.get("leaf_colour", "#7C9A5B")
        motif = (
            "".join(
                f'<circle cx="{11 + dx}" cy="{11 + dy}" r="3" fill="{accent}"/>'
                for dx, dy in ((0, -3.5), (3.5, 0), (0, 3.5), (-3.5, 0))
            )
            + '<circle cx="11" cy="11" r="1.8" fill="#F2D27A"/>'
            + f'<ellipse cx="3" cy="19" rx="3" ry="1.5" fill="{leaf}"/>'
        )
    elif kind == "sequins":
        size = 8
        motif = (
            f'<circle cx="2" cy="2" r="1.2" fill="{accent}" opacity=".8"/>'
            f'<circle cx="6" cy="6" r="1" fill="{accent}" opacity=".5"/>'
        )
    elif kind == "lace":
        size = 10
        motif = f'<circle cx="5" cy="5" r="2.6" fill="none" stroke="{accent}" stroke-width=".8"/>'
    defs = (
        f'<pattern id="{pid}" width="{size}" height="{size}" patternUnits="userSpaceOnUse">'
        f'<rect width="{size}" height="{size}" fill="{base}"/>{motif}</pattern>'
    )
    return defs, f"url(#{pid})"


def _shoe(kind: str, colour: str, x: int, skin: str) -> str:
    if kind in ("sneakers", "chunky"):
        h = 16 if kind == "chunky" else 12
        return (
            f'<rect x="{x - 12}" y="{382 - h}" width="24" height="{h}" rx="6" fill="{colour}" '
            f'stroke="{OUTLINE}"/>'
            f'<rect x="{x - 12}" y="{378}" width="24" height="4" rx="2" fill="#00000018"/>'
        )
    if kind in ("pumps", "heels"):
        return f'<path d="M{x - 6} 366 L{x + 6} 366 L{x + 4} 372 Z" fill="{skin}"/>' + _path(
            f"M{x - 9} 370 Q{x} 364 {x + 9} 370 L{x + 4} 386 L{x - 4} 386 Z", colour
        )
    if kind == "loafers":
        return (
            f'<rect x="{x - 11}" y="370" width="22" height="13" rx="4" fill="{colour}" stroke="{OUTLINE}"/>'
            + _line(f"M{x - 5} 374 L{x + 5} 374", "#FFFFFF55")
        )
    if kind == "flats":
        return f'<ellipse cx="{x}" cy="379" rx="11" ry="6" fill="{colour}" stroke="{OUTLINE}"/>'
    if kind == "platform":
        return (
            f'<rect x="{x - 11}" y="366" width="22" height="12" rx="4" fill="{colour}" stroke="{OUTLINE}"/>'
            f'<rect x="{x - 12}" y="377" width="24" height="9" rx="2" fill="#3A2618"/>'
        )
    if kind == "sandals":
        return (
            f'<ellipse cx="{x}" cy="378" rx="9" ry="7" fill="{skin}"/>'
            + _line(f"M{x - 8} 374 L{x + 8} 374", colour, 3)
            + _line(f"M{x - 7} 381 L{x + 7} 381", colour, 3)
        )
    if kind == "slippers":
        return _path(
            f"M{x - 10} 382 Q{x - 9} 370 {x} 368 Q{x + 9} 370 {x + 10} 382 Q{x} 388 {x - 10} 382 Z", colour
        )
    return f'<ellipse cx="{x}" cy="379" rx="11" ry="6" fill="{colour}"/>'


def _hair(style: str, colour: str, front: bool) -> str:
    if front:
        return _path("M161 58 Q162 36 180 36 Q198 36 199 58 Q190 46 180 46 Q170 46 161 58 Z", colour)
    if style == "long":
        return _path("M157 60 Q156 32 180 32 Q204 32 203 60 L209 124 Q180 132 151 124 Z", colour)
    if style == "bun":
        return f'<circle cx="180" cy="33" r="11" fill="{colour}"/>'
    if style == "ponytail":
        return _path("M196 44 Q214 52 208 96 Q204 104 200 96 Q206 62 192 52 Z", colour)
    if style == "bob":
        return _path("M158 60 Q156 32 180 32 Q204 32 202 60 L204 86 Q180 92 156 86 Z", colour)
    return ""


def _bag(spec: dict) -> str:
    kind, c = spec.get("kind"), spec.get("colour", "#8B5A3C")
    if kind == "tote":
        return _line("M226 240 Q238 220 250 240", c, 2.5) + _path("M220 238 L256 238 L258 282 L218 282 Z", c)
    if kind == "fringe":
        fringe = "".join(_line(f"M{x} 232 L{x} 246", c, 1.5) for x in range(140, 166, 4))
        return _line("M208 104 L150 214", c, 2) + _path("M136 210 L166 210 L166 232 L136 232 Z", c) + fringe
    if kind == "clutch":
        return _path("M118 228 L144 228 L144 242 L118 242 Z", c) + _line("M118 234 L144 234", "#00000030")
    return ""


def _figure(look_id: str, art: dict) -> tuple[str, str]:
    """(defs, body) of the dressed figure."""
    skin, hair = art.get("skin", DEFAULT_SKIN), art.get("hair", {})
    hair_style, hair_colour = hair.get("style", "long"), hair.get("colour", DEFAULT_HAIR)
    top, bottom, dress = art.get("top"), art.get("bottom"), art.get("dress")
    outer, shoes, bag = art.get("outer"), art.get("shoes", {}), art.get("bag")
    defs, parts = [], [_hair(hair_style, hair_colour, front=False)]
    parts += [_path(d, skin) for d in LEGS]

    def fill(key: str, spec: dict) -> str:
        d, f = _pattern(f"{look_id}-{key}", spec)
        defs.append(d)
        return f

    if bottom:
        f = fill("bottom", bottom)
        parts.append(_path(BOTTOMS[bottom["kind"]], f))
        if bottom.get("detail") == "jeans":
            parts += [_line("M166 232 L164 370", "#FFFFFF40"), _line("M194 232 L196 370", "#FFFFFF40")]
        if bottom.get("detail") == "cuffs":
            parts += [
                f'<rect x="{x}" y="358" width="20" height="10" rx="3" fill="{bottom["colour"]}" '
                f'stroke="#FFFFFF30"/>'
                for x in (155, 185)
            ]
        if bottom.get("detail") == "pockets":
            parts += [
                _path("M144 276 L158 276 L158 302 L144 302 Z", f),
                _path("M202 276 L216 276 L216 302 L202 302 Z", f),
            ]
        parts.append(_line("M157 196 L203 196", "#00000025", 2))
    for x in FEET:
        parts.append(_shoe(shoes.get("kind", "flats"), shoes.get("colour", "#3E2A1E"), x, skin))
    parts += [_path(d, skin) for d in ARMS]
    parts += [f'<circle cx="{x}" cy="{y}" r="7" fill="{skin}"/>' for x, y in HANDS]
    if dress and dress["kind"] == "evening":
        parts.append(_path("M148 102 L212 102 L206 150 L154 150 Z", skin))  # bare shoulders
    if top:
        f = fill("top", top)
        sleeves = top.get("sleeves", "long")
        if sleeves in SLEEVES:
            parts += [_path(d, f) for d in SLEEVES[sleeves]]
        parts.append(_path(TOPS[top.get("fit", "tucked")], f))
        kind = top.get("kind")
        if kind == "hoodie":
            parts += [
                _path("M160 100 Q180 82 200 100 Q180 112 160 100 Z", top["colour"]),
                _line("M174 104 L172 140", "#FFFFFF80"),
                _line("M186 104 L188 140", "#FFFFFF80"),
                _path("M158 186 L202 186 L206 214 L154 214 Z", top["colour"]),
            ]
        elif kind == "shirt":
            parts += [
                _path("M168 100 L180 118 L166 114 Z", f),
                _path("M192 100 L180 118 L194 114 Z", f),
                _line("M180 118 L180 196", "#00000025"),
            ]
        elif kind == "tee" or kind == "sweater":
            parts.append(_path("M168 102 Q180 114 192 102 Z", skin))
            if kind == "sweater":
                parts.append(_line("M152 210 L208 210", "#00000025", 3))
        else:  # blouse: a V neckline
            parts.append(_path("M168 102 L180 126 L192 102 Z", skin))
        if top.get("detail") == "ruffles":
            parts += [
                _line(f"M168 {y} q3 4 6 0 q3 4 6 0 q3 4 6 0 q3 4 6 0", "#FFFFFFAA") for y in (134, 150, 166)
            ]
        if top.get("detail") == "embroidery":
            gold = top.get("detail_colour", "#C9A227")
            parts += [
                _line("M166 104 L180 128 L194 104", gold, 2.5),
                _line("M180 128 L180 196", gold, 2),
                _line("M155 192 L205 192", gold, 3),
                _line("M126 222 L140 224", gold, 3),
                _line("M234 222 L220 224", gold, 3),
            ]
    if outer:
        c, kind = outer["colour"], outer["kind"]
        if kind == "track":
            parts += [_path(d, c) for d in SLEEVES["long"]]
            parts += [_line("M146 106 L131 226", "#FFFFFF", 2.5), _line("M214 106 L229 226", "#FFFFFF", 2.5)]
            parts.append(_path("M146 100 L214 100 L212 150 L212 208 L148 208 L148 150 Z", c))
            parts += [
                _line("M180 104 L180 208", "#FFFFFFAA", 2),
                _path("M166 96 L194 96 L194 106 L166 106 Z", c),
            ]
        else:
            hem = 300 if kind == "trench" else 228
            left = f"M148 100 L172 100 L172 132 L167 {hem} L142 {hem} L146 220 L150 150 Z"
            parts += [_path(d, c) for d in SLEEVES["long"]]
            parts += [_path(left, c), _path(_mirror(left), c)]
            lapel = "M172 100 L172 146 L157 112 Z"
            parts += [
                _path(lapel, c),
                _path(_mirror(lapel), c),
                _path(lapel, "#00000018"),
                _path(_mirror(lapel), "#00000018"),
            ]
            if kind == "trench":
                parts += [
                    f'<rect x="143" y="194" width="29" height="8" fill="{c}" stroke="{OUTLINE}"/>',
                    f'<rect x="188" y="194" width="29" height="8" fill="{c}" stroke="{OUTLINE}"/>',
                ]
            else:
                parts.append(f'<circle cx="169" cy="180" r="2.5" fill="{OUTLINE}"/>')
    if dress:
        f = fill("dress", dress)
        if dress["kind"] == "maxi":
            parts += [_path(d, f) for d in SLEEVES["short"]]
        parts.append(_path(DRESSES[dress["kind"]], f))
        if dress["kind"] == "maxi":
            parts.append(_path("M168 102 L180 124 L192 102 Z", skin))
        else:
            parts += [
                _line("M162 114 L164 102", dress["colour"], 2),
                _line("M198 114 L196 102", dress["colour"], 2),
            ]
    if bag:
        parts.append(_bag(bag))
    parts += [
        _path("M172 80 L188 80 L188 104 L172 104 Z", skin),
        f'<ellipse cx="180" cy="60" rx="19" ry="23" fill="{skin}"/>',
        _hair(hair_style, hair_colour, front=True),
    ]
    return "".join(defs), "".join(parts)


def render(look_id: str, title: str, family_label: str, colour: str, art: dict | None = None) -> str:
    art = art or {
        "top": {"kind": "tee", "colour": colour},
        "bottom": {"kind": "straight", "colour": "#8E8E8E"},
    }
    defs, body = _figure(look_id, art)
    t = escape(title)
    return "".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 420" role="img" aria-label="{t} · '
            f'{escape(family_label)}">',
            '<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">',
            f'<stop offset="0" stop-color="{colour}" stop-opacity="0.22"/>',
            f'<stop offset="1" stop-color="{colour}" stop-opacity="0.05"/>',
            f"</linearGradient>{defs}</defs>",
            '<rect width="360" height="420" fill="#FBFAF7"/><rect width="360" height="420" fill="url(#bg)"/>',
            '<ellipse cx="180" cy="390" rx="62" ry="8" fill="#00000014"/>',
            body,
            "</svg>",
        ]
    )
