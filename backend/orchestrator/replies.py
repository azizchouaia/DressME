"""Answers written from the agent's own facts, without the LLM: exact, instant, never "here is a JSON object".

The LLM writes only when no template fits (small talk the rules do not know, free questions).
"""

from __future__ import annotations

import re

from .understand import norm

CITIES = ["tunis", "la marsa", "ariana", "ben arous", "manouba", "sousse", "sfax", "monastir", "nabeul", "hammamet",
          "bizerte", "kairouan", "gabes", "djerba", "mahdia", "lac", "menzah", "carthage"]

SMALL_TALK = [
    (r"^(hi|hello|hey|salut|bonjour|bonsoir|aslema|ahla|salam|marhba)\b",
     "Hi! I'm your DressMe assistant. I can choose your outfit of the day, judge a piece before you buy it, find it "
     "in local shops, show your wardrobe or your style. What would you like?"),
    (r"\b(who are you|what are you|what can you do|t'es qui|tu es qui|chkoun enti|que sais-tu faire|help|aide)\b",
     "I'm DressMe's assistant: a team of AI agents behind one chat. The stylist builds outfits from your own clothes, "
     "Smart Buy tells you BUY / THINK / SKIP before you pay, local shops finds pieces in Tunisia, and I can show your "
     "wardrobe, your style and the challenges. Write, speak or send a photo."),
    (r"^(thanks|thank you|merci|chokran|y3aychek|yaatik saha|top|great|super|parfait|nice)\b",
     "You're welcome! Anything else: an outfit for tomorrow, a piece to judge, a shop to find?"),
    (r"^(bye|goodbye|au revoir|bslema|ciao)\b", "See you soon, and enjoy your outfit!"),
]


def small_talk(text: str) -> str | None:
    low = norm(text)
    for rx, answer in SMALL_TALK:
        if re.search(rx, low):
            return answer
    return None


def city_of(text: str) -> str | None:
    low = norm(text)
    return next((c.title() for c in CITIES if re.search(rf"\b{re.escape(c)}\b", low)), None)


YES = {"yes", "y", "yeah", "yep", "oui", "ouais", "ey", "eyh", "ih", "sure", "of course", "bien sûr", "ok", "okay", "true"}
NO = {"no", "n", "nope", "non", "le", "la", "lé", "false", "not really", "pas vraiment"}


def yes_no(text: str) -> bool | None:
    low = norm(text).strip(" .!?")
    first = re.split(r"[ ,.!]", low)[0] if low else ""
    if low in YES or first in YES or re.search(r"\b(i need it|j'en ai besoin|for a (wedding|party|event))\b", low):
        return True
    if low in NO or first in NO or re.search(r"\b(i don'?t need|pas besoin|just because)\b", low):
        return False
    return None


def account_of(user_id: str) -> dict:
    try:
        from api.routes.auth import user_by_id

        return user_by_id(user_id) or {}
    except Exception:  # noqa: BLE001
        return {}


def clean(s: str) -> str:
    """Fix text read with the wrong encoding ('10 Ã— 10' -> '10 × 10') and doubled words ('denim denim')."""
    s = str(s)
    if "Ã" in s or "â" in s:
        for enc in ("cp1252", "latin-1"):
            try:
                s = s.encode(enc).decode("utf-8")
                break
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
    return re.sub(r"\b(\w+) \1\b", r"\1", s)


def _names(items, key=("name", "label", "subcategory", "item", "title")) -> list[str]:
    out = []
    for it in items or []:
        if isinstance(it, dict):
            out.append(clean(next((str(it[k]) for k in key if it.get(k)), str(it.get("id", "")))))
        else:
            out.append(clean(it))
    return [n for n in out if n]


def from_facts(agent: str | None, p: dict) -> str | None:
    """The answer for this agent's result, or None to let the LLM write."""
    if not isinstance(p, dict) or not agent:
        return None
    r = p.get("result") if isinstance(p.get("result"), dict) else p
    if agent == "smartbuy" and r.get("verdict"):
        word = {"buy": "BUY ✅", "think": "THINK 🤔", "skip": "SKIP ✋"}.get(r["verdict"], r["verdict"].upper())
        head = f"{word} — {r.get('piece') or 'this piece'}, score {r.get('score')}/100."
        body = r.get("explanation") or "; ".join(r.get("reasons") or [])
        extra = f" It makes {r['new_outfits']} new outfits with your clothes." if r.get("new_outfits") else ""
        return f"{head} {body}{extra}".strip()
    if agent == "stylist" and isinstance(r.get("reply"), str) and r["reply"].strip():
        return clean(r["reply"].strip())
    if agent == "profile":
        if r.get("onboarded") is False:
            return ("I don't know your style yet. Open My style and swipe 10 looks (right if you like, left if not): "
                    "it takes one minute, then I can tell you.")
        tops = r.get("top_styles") or []
        if tops:
            parts = [f"{s.get('style')} ({round(100 * float(s.get('share') or 0))} %)" for s in tops[:3] if isinstance(s, dict)]
            return ("From your swipes, your style is " + ", ".join(parts)
                    + ". Every outfit I propose follows it; open My style to see what I learnt.")
    if agent == "taste":
        return "Noted! I'll remember it and show you more of what you like in your next outfits and suggestions."
    if agent == "wardrobe":
        items = r.get("items") or []
        if not items:
            return "Your wardrobe is empty for now. Open Wardrobe and add a photo of a piece to start."
        names = _names(items)
        more = f" and {len(names) - 8} more" if len(names) > 8 else ""
        return f"You have {len(items)} pieces: {', '.join(names[:8])}{more}. Open Wardrobe to see them on the rails."
    if agent == "localshop":
        res = r.get("results") or r.get("products") or []
        if r.get("question"):
            return str(r["question"])
        if not res:
            return "I found nothing in the local shops for that. Try another colour, a bigger budget or another city."
        lines = []
        for x in res[:3]:
            price = f"{round(x['price_tnd'])} TND" if isinstance(x, dict) and x.get("price_tnd") else "price on the site"
            lines.append(f"{x.get('item') or x.get('name')} at {x.get('shop')} ({price})" if isinstance(x, dict) else str(x))
        return f"I found {len(res)} pieces in local shops. Best matches: " + "; ".join(lines) + "."
    if agent == "challenges":
        ch = r.get("challenges") or []
        if not ch:
            return "There is no open challenge right now. Check again soon in Share & challenges."
        names = _names(ch, ("title", "name"))
        return f"{len(ch)} challenges for you: " + ", ".join(names[:4]) + ". Open Share & challenges to join one."
    return None


# ---------------------------------------------------------------- every question gets an answer
CAN_DO = ("I can choose your outfit for today or tomorrow, build an outfit around one of your pieces, tell you "
          "BUY / THINK / SKIP before you buy something, find a piece in Tunisian shops, show your wardrobe and your "
          "style, or open the challenges.")

OUT_OF_SCOPE = ("I'm DressMe's style assistant, so I can't help with that one. " + CAN_DO
                + " What would you like?")

UNSURE = ("I'm not sure I understood. " + CAN_DO + " For example: \"what should I wear tomorrow?\" or "
          "\"should I buy a black jacket at 200 TND?\"")

_FASHION = (r"\b(wear|outfit|look|style|cloth|clothes|dress|shirt|t-shirt|jean|pant|trouser|skirt|shoe|sneaker|boot|"
            r"jacket|coat|blazer|suit|costume|sweater|pull|hoodie|bag|hat|scarf|colou?r|fabric|wash|iron|size|fit|"
            r"fashion|mode|tenue|v[êe]tement|habit|chemise|robe|pantalon|chaussure|veste|couleur|taille|laver|repasser|"
            r"wardrobe|closet|garde-robe|buy|shop|store|boutique|price|tnd|dt|wedding|mariage|interview|party|soir[ée]e|"
            r"elbes|nelbes|7wayej|hwayej|9mejja|sabbat|kabbot)\b")
_OFF_TOPIC = (r"\b(capital of|president|politic|election|football|match score|recipe|cook|math|equation|calculate|"
              r"code|python|java|program|homework|exam|translate|weather in|news|stock|bitcoin|crypto|movie|film|"
              r"song|lyrics|joke|blague|medical|doctor|symptom|religion|game)\b")


def is_fashion(text: str) -> bool:
    return bool(re.search(_FASHION, norm(text)))


def off_topic(text: str) -> bool:
    """Clearly not about clothes (and no clothes word in it): decline politely, without the LLM."""
    low = norm(text)
    return bool(re.search(_OFF_TOPIC, low)) and not is_fashion(low)


_BAD = (r"(i can'?t answer|i cannot answer|i don'?t have (any )?(specific )?(information|function|module)|"
        r"\bjson\b|function call|the function|tool call|documentation|as an ai|i'?m not able to|i am not able to|"
        r"provide more context|payload|probe_image|\{\s*\")")


def guard(reply: str, user_text: str) -> str:
    """Never a blank, technical or 'I can't answer' reply: fall back to what DressMe can do."""
    r = (reply or "").strip()
    if not r or re.search(_BAD, r, re.I):
        return UNSURE if is_fashion(user_text) else OUT_OF_SCOPE
    return r


GENERAL_PROMPT = (
    "You are DressMe's style assistant in Tunisia. Answer the user's last message yourself, in their language, "
    "in 2 or 3 short sentences.\n"
    "- About clothes, outfits, colours, fabrics, care (washing, ironing), sizes, style or fashion in general: give a "
    "useful, concrete answer, then offer one thing the app can do for them.\n"
    "- About anything else: say kindly that you only help with clothes and style, then suggest two things you can "
    "do: choose an outfit, judge a purchase (BUY / THINK / SKIP), find a piece in local shops.\n"
    "Never mention functions, tools, JSON, modules or documentation. Never invent the user's clothes."
)
