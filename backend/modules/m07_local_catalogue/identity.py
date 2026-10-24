"""Who the BO6 agent is: its card (identity, skills, contract, rules).

One agent per BO: `localshop` groups M7 (catalogue search) and M14 (boutique / stylist mode) as skills.
The orchestrator (BO8) reads the card to know WHEN to call it and WHAT to do with the answer.
Served at GET /m07/card. The tool description is built from it, so they never drift apart.
"""

VERSION = "1.6.0"

CARD = {
    "id": "dressme.bo6.localshop",
    "name": "localshop",
    "display_name": "Local shops",
    "version": VERSION,
    "owner": "BO6",
    "module": "M7",
    "role": "Finds pieces sold by Tunisian shops and brands, with prices in dinars (TND), for a request, "
    "a wardrobe gap, a photo or the user's style.",
    "persona": "A friend who knows the Tunisian shops: concrete, local, never invents a product.",
    "llm": "qwen2.5:7b, local with Ollama (llm.py): understands requests the rules miss, writes texts "
    "for M14; never picks products, prices or stylists; off -> rules",
    "rules": [
        "Only shops, products and prices returned by the catalogue; never invented.",
        "Prices are in TND, as the shop shows them.",
        "A colour asked for is strict; a relaxed filter (city, stock, colour) is always said in `note`.",
        "When the request is unclear, ask ONE question the user can answer instead of guessing.",
        "The LLM only reads and writes; products, prices and scores come from the catalogue and the code.",
        "An occasion with no piece named searches the pieces worn for it, and says which in `note`.",
        "A season and a usual budget learned from memory only re-rank; a budget the user says always wins.",
        "Compatibility with the wardrobe comes from M2, never the LLM; `sources` says real or simulation.",
    ],
    "when_to_use": [
        "Where can I buy this in Tunis? A linen shirt under 80 dinars. Shops near me.",
        "Requests in French, English or Tunisian darija ('sabbat ahmar', 'sbadri kahla a9al men 150 alf').",
        "An outfit for a Tunisian occasion or season: wedding (3ers), henna, Aïd, Ramadan evenings, "
        "the beach, an interview; summer or winter pieces.",
        "A missing piece from Smart Buy or the Profile (`gap`), or a photo embedding: local alternatives.",
        "The outfit of the day (BO1) with a Tunisian piece in it: call local-pieces with its item_ids.",
        "The user answers localshop's question (send `answer` + the same session_id, not the request).",
        "'Show me more' after a localshop search (send next_page=true + the same session_id).",
    ],
    "when_not_to_use": [
        "Should I buy it? -> smartbuy",
        "What should I wear from what I own? -> stylist",
        "Add this photo to my wardrobe -> wardrobe",
    ],
    "skills": {
        "search": "M7 catalogue search: text (FR/EN/darija), gap, photo or style -> Tunisian pieces in TND",
        "occasion": "Tunisian occasions and seasons -> the pieces worn for them, seasonal pieces first",
        "usual_budget": "no budget said -> the user's usual budget per type, learned from memory, re-ranks",
        "wardrobe_fit": "results of a user: which pieces of their wardrobe (M1) each one goes with (M2)",
        "outfits": "POST /m07/outfits: outfits from the wardrobe around one local piece (M2 /complete)",
        "local_pieces": "POST /m07/local-pieces: Tunisian pieces to complete or change an outfit of the day",
        "answer": "answer to the last question (gender, budget, piece) -> refined results",
        "more": "next page of the last search of the session",
        "feedback": "useful / bought -> the user's memory",
        "history": "past searches of this user",
        "boutique": "M14 stylist mode for a shop's clients",
    },
    "inputs": {
        "required": ["query, gap, category/subcategory or image_embedding (or answer / next_page)"],
        "optional": [
            "city",
            "max_price_tnd",
            "min_price_tnd",
            "color",
            "gender",
            "occasion",
            "season",
            "user_id",
            "style_vector",
            "k",
            "session_id",
            "language",
        ],
    },
    "outputs": ["results", "parsed", "total_matches", "note", "question", "next_actions", "decision_id"],
    "handoff": [
        {"action": "judge", "label": "Should I buy one of these?", "tool": "smartbuy", "args": {}},
        {"action": "try_on", "label": "Try it on my avatar", "tool": "tryon", "args": {}},
    ],
    "depends_on": {
        "M1": "the user's wardrobe (BO3), simulated until merged",
        "M2": "compatibility and outfits (BO1), simulated until merged",
        "M5": "style vector (BO4)",
        "M14": "boutique mode (BO6)",
    },
    "languages": ["en", "fr", "ar"],
}


def tool_description() -> str:
    """Same text as the orchestrator's shared.agent_card.describe() (BO8), plus how to use the result."""
    usage = (
        " If the result has `question`, ask it, then call again with `answer` and the same session_id."
        " Follow `next_actions` to chain smartbuy / stylist. Never change a price."
    )
    try:
        from shared.agent_card import describe

        return describe(CARD) + usage
    except ImportError:  # shared/agent_card.py comes with the orchestrator branch (BO8)
        pass
    c = CARD
    return (
        f"{c['name']} ({c['module']}, {c['owner']}): {c['role']} "
        f"Skills: {', '.join(f'{k}: {v}' for k, v in c['skills'].items())}. "
        f"Use when: {'; '.join(c['when_to_use'])}. Do not use when: {'; '.join(c['when_not_to_use'])}."
        + usage
    )
