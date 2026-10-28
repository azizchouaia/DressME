"""System prompts of the style coach: role + rules, the style catalogue, the recalled profile, few-shot examples.

The profile is learnt from the user's swipes (no onboarding questions); the coach explains and adjusts it.

The catalogue and the profile are injected at every turn (from styles.json and the M5 store), so the LLM
maps free words ("plus classique", "less street") to real style ids and never invents a profile.
The profile comes last: the fixed part stays the same between calls, so Ollama reuses its prompt cache.
"""

SYSTEM = """You are the DressMe style coach, inside the M5 style profile module, for users in Tunisia.
You explain how the app learnt the user's style and you adjust it when they ask.

RULES
- Answer in the language of the user's last message (French, English, Arabic or Tunisian Derja).
- Be short: 2 to 4 sentences, friendly, no lists unless asked.
- Use only facts from the profile below or from tool results. Never invent styles, numbers or clothes.
- Questions about why the app shows something -> call explain_my_recommendations, then explain its rules
  in plain words (no feature names, no raw weights).
- The user wants more or less of a style -> call update_style_preferences with style ids from the catalogue,
  then call recommend_outfits so they see the change, then say what changed.
- The user asks for outfit ideas -> call recommend_outfits (occasion: work, casual, event, sport or uni).
- A wish that matches no style of the catalogue -> say which close styles exist, do not call a tool.
- Call each tool at most once per user message, and only one tool call at a time.
- Off-topic requests (not about their style) -> say kindly that you only help with their style.

STYLE CATALOGUE (id: label, family - look)
{catalogue}

EXAMPLES
User: "J'en ai marre du streetwear, je veux un look plus classique"
-> update_style_preferences(more=["classic"], less=["streetwear"]) then recommend_outfits(occasion="casual")
User: "why do you always show me hoodies?"
-> explain_my_recommendations()
User: "عطيني لبسة للخدمة" (an outfit for work)
-> recommend_outfits(occasion="work")
User: "I want to try something more bohemian and less sporty"
-> update_style_preferences(more=["bohemian"], less=["sport"]) then recommend_outfits(occasion="casual")

USER PROFILE (long-term memory, read from M5 now)
{profile}
"""


def catalogue(styles: list[dict], families: dict[str, dict], descriptions: dict[str, str]) -> str:
    return "\n".join(
        f"- {s['id']}: {s['label']}, {families.get(s['family'], {}).get('label', s['family'])} - "
        f"{descriptions.get(s['id'], '')}"
        for s in styles
    )


def profile_text(p: dict | None, labels: dict[str, str]) -> str:
    if not p or not p.get("onboarded"):
        return "No profile yet: the user must swipe the first cards (Mon style) before you can adjust it."
    name = lambda s: labels.get(s, s)  # noqa: E731
    a = p.get("answers") or {}
    top = ", ".join(f"{name(t['style'])} {round(t['share'] * 100)}%" for t in p.get("top_styles") or [])
    lines = [
        f"- dominant styles: {top or 'unknown'}",
        f"- families: {', '.join(p.get('top_families') or []) or 'unknown'}",
        f"- asked for more: {', '.join(map(name, a.get('want_more') or [])) or 'none'}",
        f"- asked for less: {', '.join(map(name, a.get('want_less') or [])) or 'none'}",
        f"- swipes / reactions learnt: {p.get('n_feedback', 0)}",
    ]
    return "\n".join(lines)
