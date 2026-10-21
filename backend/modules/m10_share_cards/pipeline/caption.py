"""Caption and alt text. Template-based for now; M8 (LLM layer) can replace `caption` later
without changing the agent contract (rule 3 · mock first, real model later)."""

HASHTAG = "#MadeWithDressMe"

TEMPLATES_FR = {
    "outfit": "Mon look du jour : {items} {tag}",
    "board": "Composé par moi : {items} {tag}",
    "tryon": "Essayé sur mon avatar, sans selfie. {items} {tag}",
    "recap": "Mon mois en tenues. {stats} {tag}",
    "giveaway": "Je donne : {items}. Écris-moi si ça t'intéresse ! {tag}",
    "challenge": "{title} : {items} {tag}",
    "style_timeline": "Comment mon style a changé. {stats} {tag}",
    "trip": "Mon lookbook de voyage : {items} {tag}",
    "poll": "Je l'achète ou pas ? Vote avec le lien. {tag}",
}
# Tunisian derja in Latin letters (how people write it on WhatsApp / Instagram)
TEMPLATES_TN = {
    "outfit": "El lebsa mte3 el youm : {items} {tag}",
    "board": "Rakkabtha wa7di : {items} {tag}",
    "tryon": "Jarrabtha 3al avatar mte3i, bla selfie. {items} {tag}",
    "recap": "Chhari fil lebsa. {stats} {tag}",
    "giveaway": "Nhabbat {items} bla flous. Ken t7ebha ab3athli ! {tag}",
    "challenge": "{title} : {items} {tag}",
    "style_timeline": "Kifech tbaddel style mte3i. {stats} {tag}",
    "trip": "Lebset el safra : {items} {tag}",
    "poll": "Nechriha walla le ? Votiw bel lien. {tag}",
}

TEMPLATES = {
    "outfit": "Today's look: {items} {tag}",
    "board": "Styled it myself: {items} {tag}",
    "tryon": "Tried it on my avatar, no selfie needed. {items} {tag}",
    "recap": "My month in outfits. {stats} {tag}",
    "giveaway": "Giving away: {items}. Message me if you want it! {tag}",
    "challenge": "{title}: {items} {tag}",
    "style_timeline": "How my style changed. {stats} {tag}",
    "trip": "Trip lookbook: {items} {tag}",
    "poll": "Should I buy this? Vote with the link. {tag}",
}


def _items(labels: list[str]) -> str:
    labels = [x for x in labels if x]
    if not labels:
        return ""
    return labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " + " + labels[-1]


def caption(
    kind: str, labels: list[str], title: str | None, stats: list[tuple[str, str]], language: str = "en"
) -> str:
    """if/else on the language: en (default), fr, tn (Tunisian derja in Latin letters)."""
    stats_txt = " · ".join(f"{label}: {value}" for label, value in stats[:3])
    table = {"fr": TEMPLATES_FR, "tn": TEMPLATES_TN}.get(language, TEMPLATES)
    text = table.get(kind, "{items} {tag}").format(
        items=_items(labels), stats=stats_txt, title=title or "Challenge", tag=HASHTAG
    )
    return " ".join(text.split())


def alt_text(kind: str, items: list[tuple[str, str]], title: str | None) -> str:
    """Accessible description of the card (screen readers, Instagram alt text)."""
    head = f"DressMe {kind.replace('_', ' ')} card" + (f" titled “{title}”" if title else "")
    if not items:
        return head + "."
    parts = ", ".join(f"{label} ({category})" for label, category in items)
    return f"{head}, flat-lay of: {parts}."
