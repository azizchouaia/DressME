"""Four slides from the team plan: BO8 feature 14 and BO9 feature 13."""
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
    add_text(slide, kicker, 0.55, 0.28, 10, 0.32, 13, True, MUTED)
    add_text(slide, page, 11.6, 7.05, 1.2, 0.28, 12, False, MUTED, PP_ALIGN.RIGHT)
    add_text(slide, "DressMe  ·  team plan, 10 Oct 2026", 0.55, 7.05, 6, 0.28, 12, False, MUTED)


def card(slide, x, y, w, h):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = CARD
    shape.line.color.rgb = RULE
    shape.adjustments[0] = 0.08
    return shape


s = prs.slides.add_slide(blank)
chrome(s, "FROM THE TEAM PLAN", "01")
add_text(s, "Two missions.\nTwo selected ideas.", 0.55, 0.7, 8, 1.5, 36, True)
card(s, 0.55, 2.55, 6, 3.5)
add_text(s, "BO8  ·  feature 14", 0.85, 2.75, 5.4, 0.35, 14, True, MUTED)
add_text(s, "Conversational assistant", 0.85, 3.2, 5.4, 0.7, 24, True)
add_text(s, "Understands the request, keeps memory, calls the other agents in order, and returns one answer.", 0.85, 4.1, 5.3, 1.4, 16, False)
card(s, 6.8, 2.55, 6, 3.5)
add_text(s, "BO9  ·  feature 13", 7.1, 2.75, 5.4, 0.35, 14, True, MUTED)
add_text(s, "Faceless 3D try-on", 7.1, 3.2, 5.4, 0.7, 24, True)
add_text(s, "A body from measurements. Outfits shown on that body. No face stored.", 7.1, 4.1, 5.3, 1.4, 16, False)
add_notes(
    s,
    "Open from the team document, not from a new idea. "
    "BO8 is feature 14, the conversational assistant, and it is in the MVP. "
    "Its job is to understand the request, keep memory, decide which agents to call and in what order, and merge one answer. "
    "An open chatbot was rejected. "
    "BO9 is feature 13, the faceless 3D try-on, phase 2. "
    "Its job is an SMPL-X body from measurements and the outfit rendered on it. "
    "I will take three points from those two missions, and only the parts we actually moved this week.",
)

s = prs.slides.add_slide(blank)
chrome(s, "IDEA 1  ·  BO8", "02")
add_text(s, "Call the right agent,\nin the right order", 0.55, 0.7, 12, 1.4, 34, True)
add_text(s, "The plan says the assistant decides the sequence. It does not answer from itself.", 0.55, 2.2, 12, 0.45, 18, False, MUTED)
rows = [
    ("Pushed this week", "A LangGraph orchestrator. Each module joins through one tool."),
    ("What it knows", "A card per agent: when to call it, and when not to."),
    ("The limit", "One agent at a time. A next step only if that agent offers it. Stop at three."),
]
for i, (title, body) in enumerate(rows):
    y = 2.9 + i * 1.2
    card(s, 0.55, y, 12.2, 1.05)
    add_text(s, title, 0.85, y + 0.25, 3.2, 0.55, 18, True)
    add_text(s, body, 4.2, y + 0.25, 8.1, 0.55, 18, False)
add_notes(
    s,
    "This is feature 14. "
    "On 21 October we pushed the LangGraph orchestrator so each module can join through one tool. "
    "The planner reads the agent card and calls one tool. Agents do not call each other. "
    "If the result offers a next step, it may follow it, up to three calls, then the writer makes one reply. "
    "The document's example plan is weather, profile, recommend, then render try-on. "
    "Say that the sequence is the product. The chat is only where the person types.",
)

s = prs.slides.add_slide(blank)
chrome(s, "IDEA 2  ·  BO8", "03")
add_text(s, "Remember the person.\nKeep the facts.", 0.55, 0.7, 12, 1.4, 34, True)
add_text(s, "The plan asks for conversation memory and guardrails. An open chatbot was rejected.", 0.55, 2.2, 12, 0.45, 18, False, MUTED)
card(s, 0.55, 2.95, 6, 3.1)
add_text(s, "Taste  ·  pushed 21 Oct", 0.85, 3.15, 5.4, 0.4, 14, True, MUTED)
add_text(s, "An outfit or a purchase is ranked from this person's likes, dislikes, and saved looks.", 0.85, 3.75, 5.3, 1.6, 20, True)
card(s, 6.8, 2.95, 6, 3.1)
add_text(s, "Talk  ·  pushed 21 Oct", 7.1, 3.15, 5.4, 0.4, 14, True, MUTED)
add_text(s, "The reply can quote that score. A new preference is saved. The score, price, and size stay.", 7.1, 3.75, 5.3, 1.6, 20, True)
add_notes(
    s,
    "This is the memory and the guardrail inside BO8, not a new objective. "
    "Same day, we pushed taste and talk. "
    "One FashionCLIP model. Each person has their own memory rows, not their own network. "
    "Taste ranks. Talk writes the sentence and can store a stated like or dislike in that same memory. "
    "Talk must not change the verdict, the score, the price, or the size. "
    "That is the guardrail: it is an assistant for the wardrobe, not a general chatbot.",
)

s = prs.slides.add_slide(blank)
chrome(s, "IDEA 3  ·  BO9", "04")
add_text(s, "Show the outfit\non a faceless body", 0.55, 0.7, 12, 1.4, 34, True)
add_text(s, "Feature 13. SMPL-X. The clothes are a mesh on that body, served in the viewer.", 0.55, 2.2, 12, 0.45, 18, False, MUTED)
rows = [
    ("The body", "An SMPL-X body, about 1.70 m. Faceless. Shape can be changed in the viewer."),
    ("The outfit", "Shirt, shorts, and vest, reconstructed with ReMU and skinned onto the body."),
    ("The poses", "Front, Glance, and Casual, so the same outfit can be looked at standing."),
]
for i, (title, body) in enumerate(rows):
    y = 2.9 + i * 1.2
    card(s, 0.55, y, 12.2, 1.05)
    add_text(s, title, 0.85, y + 0.25, 2.6, 0.55, 18, True)
    add_text(s, body, 3.6, y + 0.25, 8.7, 0.55, 18, False)
add_notes(
    s,
    "This is feature 13, and it stands on its own. "
    "The plan asks for a faceless SMPL-X body from measurements, template garments, a GLB, and a 2D fallback. "
    "What we can show is the SMPL-X body and three reconstructed garments worn on it: shirt, shorts, vest. "
    "Three standing poses. "
    "Do not claim the body was fitted from a measured chest, waist, and hips, and do not claim the 2D fallback. "
    "The try-on agent the orchestrator can call shows those same three pieces. It does not choose the outfit.",
)

out = r"C:\Users\NADHIR\Desktop\DressMe-BO8-BO9.pptx"
prs.save(out)
print(out)
