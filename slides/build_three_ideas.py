"""Three slides: photographed piece, faceless try-on, memory."""
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

PAPER = RGBColor(0xF6, 0xF4, 0xF0)
INK = RGBColor(0x1C, 0x19, 0x17)
MUTED = RGBColor(0x6B, 0x64, 0x5C)
RULE = RGBColor(0xD9, 0xD3, 0xCB)
CARD = RGBColor(0xFF, 0xFC, 0xF8)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
blank = prs.slide_layouts[6]


def set_run(run, text, size, bold=False, color=INK, font="Calibri"):
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = font


def add_text(slide, text, x, y, w, h, size=18, bold=False, color=INK, align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.word_wrap = True
    p = frame.paragraphs[0]
    p.alignment = align
    set_run(p.add_run(), text, size, bold, color)
    return frame


def add_notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def chrome(slide, kicker, page):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = PAPER
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(0.08))
    bar.fill.solid()
    bar.fill.fore_color.rgb = INK
    bar.line.fill.background()
    add_text(slide, kicker, 0.55, 0.22, 10, 0.3, 13, True, MUTED)
    add_text(slide, page, 11.6, 7.08, 1.2, 0.28, 12, False, MUTED, PP_ALIGN.RIGHT)
    add_text(slide, "DressMe  ·  selected ideas", 0.55, 7.08, 5, 0.28, 12, False, MUTED)


def card(slide, x, y, w, h):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = CARD
    shape.line.color.rgb = RULE
    shape.adjustments[0] = 0.08
    return shape


# 1. Photographed piece
s = prs.slides.add_slide(blank)
chrome(s, "BO9  ·  IDEA 6", "01")
add_text(s, "Try a photographed piece", 0.55, 0.55, 12, 0.6, 32, True)
add_text(s, "Any piece can be visualised without being in the wardrobe.", 0.55, 1.25, 12, 0.4, 18, False, MUTED)
card(s, 0.55, 1.9, 12.2, 4.7)
add_text(s, "The piece does not have to be owned already. A photo is enough.", 0.85, 2.1, 11.6, 0.45, 18, True)
add_text(
    s,
    "The photo is reconstructed into a garment mesh. That mesh is worn on the faceless body, so the person sees a piece they found outside the wardrobe.",
    0.85, 2.65, 11.6, 1.1, 18, False,
)
add_text(
    s,
    "What we can show: the shirt, the shorts, and the vest were reconstructed with ReMU from garment photos and skinned onto the SMPL-X body. A new clothes photo can be sent to that same ReMU path from the viewer.",
    0.85, 3.9, 11.6, 1.3, 18, False,
)
add_text(s, "Based on: Outfit from a photo.", 0.85, 5.5, 11.6, 0.4, 16, True, MUTED)
add_notes(
    s,
    "This is idea 6 of the try-on list. "
    "Say: the wardrobe is not the limit. Someone can photograph a piece they do not own, and the try-on shows it on the body. "
    "The photos we already turned into worn meshes are the shirt, the shorts, and the vest, through ReMU. "
    "Do not say every new photo already comes back as a finished wearable file. Say the path is the same ReMU reconstruction, and these three are the ones on the body.",
)

# 2. Faceless try-on
s = prs.slides.add_slide(blank)
chrome(s, "BO9  ·  IDEA 1", "02")
add_text(s, "Faceless 3D avatar try-on", 0.55, 0.55, 12, 0.6, 32, True)
add_text(s, "The supervisor requirement, and the strongest differentiator.", 0.55, 1.25, 12, 0.4, 18, False, MUTED)
card(s, 0.55, 1.9, 12.2, 4.7)
add_text(s, "The person sees the look. They do not have to imagine it.", 0.85, 2.1, 11.6, 0.45, 18, True)
add_text(
    s,
    "The body is SMPL-X and it has no face. No face photo and no body photo are stored. The outfit is a 3D mesh skinned on that body, so the fit and the combination are visible.",
    0.85, 2.7, 11.6, 1.2, 18, False,
)
add_text(
    s,
    "What we can show: a body about 1.70 m, three standing poses — Front, Glance, and Casual — and the reconstructed shirt, shorts, and vest worn on it.",
    0.85, 4.1, 11.6, 1.1, 18, False,
)
add_text(s, "Based on: 3D avatar try-on.", 0.85, 5.5, 11.6, 0.4, 16, True, MUTED)
add_notes(
    s,
    "This is idea 1 of the try-on list. "
    "Say it is the requirement from the supervisor and the thing that separates the product. "
    "Faceless is a privacy choice: SMPL-X from the body shape, not a photo of the person's face. "
    "Show the viewer. Name the three garments and the three poses. "
    "The try-on agent shows those pieces. It does not decide the outfit.",
)

# 3. Memory
s = prs.slides.add_slide(blank)
chrome(s, "BO8  ·  IDEA 3", "03")
add_text(s, "An assistant that remembers", 0.55, 0.5, 12, 0.55, 32, True)
add_text(s, "Personal memory makes each conversation feel tailored.", 0.55, 1.1, 12, 0.35, 18, False, MUTED)
add_text(
    s,
    "The orchestrator does not keep the taste itself. It calls the agents that see the person's choices. Taste stores one memory per person, and the next call reads it.",
    0.55, 1.55, 12.2, 0.85, 16, False,
)
agents = [
    ("Taste", "A like, a dislike, a skip, or a saved look."),
    ("Talk", "A preference the person says in the chat, written into that same memory."),
    ("Try-on", "A reaction after seeing the look on the body."),
    ("Smart Buy", "The purchase check, with its score and price left unchanged."),
    ("Local shop", "A piece they ask for in a local shop."),
    ("Profile", "The style profile over time. A single like stays in taste."),
]
for i, (name, body) in enumerate(agents):
    col = i % 2
    row = i // 2
    x = 0.55 + col * 6.4
    y = 2.55 + row * 1.35
    card(s, x, y, 6.15, 1.2)
    add_text(s, name, x + 0.25, y + 0.15, 5.6, 0.35, 16, True)
    add_text(s, body, x + 0.25, y + 0.52, 5.6, 0.5, 14, False)
add_notes(
    s,
    "This is idea 3 of the assistant list, based on the adaptive style profile. "
    "Explain the architecture. The planner calls one agent at a time. Agents do not call each other. "
    "Taste and talk share one memory. One FashionCLIP model, one row set per person. "
    "Taste writes likes, dislikes, skips, and saves. Talk writes a preference spoken in the chat. "
    "Try-on contributes the reaction to a look. Smart Buy contributes the purchase check. Local shop contributes what they asked for nearby. "
    "Profile holds the longer style profile. A single like is not written there. "
    "The next ranking starts from taste, so the conversation follows this person. The writer still cannot change the score, the price, or the size.",
)

out = r"C:\Users\NADHIR\Desktop\DressMe-three-ideas.pptx"
prs.save(out)
print(out)
