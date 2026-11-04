"""The sentences a jury types (typos, French, Tounsi), and full conversations: the right agent every time,
a question when a detail is missing, and a helpful sentence (never an error) when an agent fails."""

import asyncio

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool

from orchestrator.graph import build_graph, route_by_rules, run_turn
from orchestrator.understand import piece_of

TOOLS = {"wardrobe", "profile", "smartbuy", "localshop", "tryon", "share", "trips", "challenges", "taste", "talk", "stylist"}

ROUTES = [
    ("Should I buy a navy blazer at 120 TND?", "smartbuy"),
    ("shoul i by a blue  costume with 320dt", "smartbuy"),
    ("should i get these white sneakers for 250 dinars", "smartbuy"),
    ("is it a good deal, a black jacket 200dt", "smartbuy"),
    ("est-ce que je dois acheter une robe rouge à 150 dt", "smartbuy"),
    ("nechri pull noir b 80 dinars?", "smartbuy"),
    ("Find a white shirt in a shop in Tunis", "localshop"),
    ("where can i buy black boots in sousse", "localshop"),
    ("ou acheter un jean bleu à tunis", "localshop"),
    ("What should I wear tomorrow for work?", "stylist"),
    ("what do i wear today", "stylist"),
    ("quoi porter pour un mariage samedi", "stylist"),
    ("chnowa nelbes ghodwa lel khedma", "stylist"),
    ("give me an outfit for the weekend", "stylist"),
    ("my black t-shirt is dirty, put it in the laundry", "stylist"),
    ("Show my wardrobe", "wardrobe"),
    ("what's in my closet", "wardrobe"),
    ("Show me the challenges", "challenges"),
    ("quels sont les défis", "challenges"),
    ("I love oversize sweaters", "taste"),
    ("what is my style", "profile"),
    ("quel est mon style", "profile"),
    ("j'adore les couleurs claires", "taste"),
    ("where can i find a black dress in tunis", "localshop"),
    ("try it on my avatar", "tryon"),
]


@pytest.mark.parametrize("text,agent", ROUTES)
def test_the_right_agent(text, agent):
    hit = route_by_rules(text, TOOLS)
    assert hit and hit.get("name") == agent, (text, hit)


@pytest.mark.parametrize("text", ["hello", "thanks!", "who are you?", "tell me a joke"])
def test_small_talk_goes_to_the_llm(text):
    assert route_by_rules(text, TOOLS) is None


def test_smart_buy_reads_the_piece():
    assert piece_of("shoul i by a blue  costume with 320dt") == {"type": "blazer", "colour": "blue", "price": 320.0}
    hit = route_by_rules("Should I buy a navy blazer at 120 TND?", TOOLS)
    assert hit["args"] == {"probe_image": "custom:blazer:navy", "price_tnd": 120.0}


def test_buy_without_a_piece_asks_then_remembers():
    first = route_by_rules("should i buy it for 90 dt?", TOOLS)
    assert "ask" in first and first["intent"] == {"tool": "smartbuy", "price": 90.0}
    second = route_by_rules("a green jacket", TOOLS, pending=first["intent"])
    assert second["name"] == "smartbuy" and second["args"] == {"probe_image": "custom:jacket:green", "price_tnd": 90.0}


def test_a_photo_alone_goes_to_smart_buy():
    hit = route_by_rules("", TOOLS, attachment={"image": "data:x", "probe": "custom:shirt:white"})
    assert hit["name"] == "smartbuy" and hit["args"]["probe_image"] == "custom:shirt:white"


# ---------------------------------------------------------------- full conversations through the graph
class Writer:
    """The LLM: only the writer is called (the rules route); it echoes the agent's facts."""

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        return AIMessage(content="Here is what I found.")


def _tool(name, fn):
    return StructuredTool.from_function(coroutine=fn, name=name, description=f"stand-in {name}")


def _graph(seen):
    async def smartbuy(probe_image: str = "", price_tnd: float | None = None, user_id: str = "", session_id: str = "") -> dict:
        seen.append(("smartbuy", probe_image, price_tnd))
        if probe_image == "custom:dress:black":
            raise ValueError("model not loaded")
        return {"verdict": "think", "score": 49, "piece": probe_image.split(":", 1)[-1]}

    async def stylist(action: str = "", message: str = "", payload: dict | None = None, user_id: str = "", session_id: str = "") -> dict:
        seen.append(("stylist", message, None))
        return {"outfits": [{"items": [{"id": "a", "name": "navy t-shirt"}]}]}

    tools = [_tool("smartbuy", smartbuy), _tool("stylist", stylist)]
    return build_graph(model=Writer(), tools=tools, rules=True)


def test_conversation_ask_then_judge_then_outfit():
    seen = []
    g = _graph(seen)
    run = lambda m: asyncio.run(run_turn(g, user_id="jury", session_id="s1", message=m))  # noqa: E731

    r1 = run("should i buy it? it's 320dt")
    assert "Which piece is it?" in r1["reply"] and not seen
    r2 = run("a blue costume")
    assert seen[-1] == ("smartbuy", "custom:blazer:blue", 320.0)
    assert r2["last_agent"] == "smartbuy" and r2["cards"][-1]["verdict"] == "think"
    r3 = run("ok and what should I wear tomorrow?")
    assert seen[-1][0] == "stylist" and r3["last_agent"] == "stylist"


def test_an_agent_error_becomes_a_helpful_sentence():
    seen = []
    g = _graph(seen)
    r = asyncio.run(run_turn(g, user_id="jury", session_id="s2", message="should I buy a black dress at 100 TND"))
    assert "couldn't finish" in r["reply"] and "photo" in r["reply"]
    assert "Traceback" not in r["reply"]


def test_answer_goes_back_with_the_key_and_replies_are_written_from_facts():
    calls = []

    async def smartbuy(probe_image: str = "", price_tnd: float | None = None, answer: dict | None = None,
                       user_id: str = "", session_id: str = "") -> dict:
        calls.append(answer)
        if not answer:
            return {"verdict": "think", "score": 54, "question": "Do you need it for an event?",
                    "question_key": "need_for_occasion"}
        return {"verdict": "buy", "score": 72, "piece": "Blue blazer", "explanation": "It completes 4 outfits."}

    g = build_graph(model=Writer(), tools=[_tool("smartbuy", smartbuy)], rules=True)
    run = lambda m: asyncio.run(run_turn(g, user_id="jury", session_id="s3", message=m))  # noqa: E731
    assert run("should I buy a blue costume at 320dt")["question"] == "Do you need it for an event?"
    r = run("yes, for a wedding")
    assert calls[-1] == {"question_key": "need_for_occasion", "value": True}
    assert r["reply"].startswith("BUY") and "It completes 4 outfits." in r["reply"]


@pytest.mark.parametrize("text", ["hello", "Bonjour !", "who are you?", "thanks!", "aslema"])
def test_small_talk_is_answered_without_the_llm(text):
    g = build_graph(model=Writer(), tools=[], rules=True)
    r = asyncio.run(run_turn(g, user_id="jury", session_id="s4", message=text))
    assert "DressMe" in r["reply"] or "welcome" in r["reply"].lower()


def test_local_shop_gets_its_own_arguments():
    hit = route_by_rules("where can i buy black boots in sousse under 200 dt", TOOLS)
    assert hit["args"] == {"query": "where can i buy black boots in sousse under 200 dt", "subcategory": "boots",
                           "color": "black", "max_price_tnd": 200.0, "city": "Sousse"}


def test_a_new_request_is_not_taken_as_an_answer():
    from orchestrator.replies import clean

    assert clean("10 Ã— 10 capsule") == "10 × 10 capsule"
    assert clean("denim denim jeans") == "denim jeans"


@pytest.mark.parametrize("text", ["what is the capital of France?", "solve this equation 2x+3=7", "who won the football match",
                                  "write me python code", "tell me a joke"])
def test_off_topic_is_declined_kindly(text):
    g = build_graph(model=Writer(), tools=[], rules=True)
    r = asyncio.run(run_turn(g, user_id="jury", session_id="s5", message=text))
    assert "style assistant" in r["reply"] and "outfit" in r["reply"]


class BadLLM(Writer):
    async def ainvoke(self, messages):
        return AIMessage(content='I can\'t answer that. The function to use is {"name": "stylist"}')


def test_never_a_technical_or_empty_answer():
    g = build_graph(model=BadLLM(), tools=[], rules=True)
    fashion = asyncio.run(run_turn(g, user_id="jury", session_id="s6", message="how do I wash a wool sweater?"))
    assert "not sure I understood" in fashion["reply"] and "function" not in fashion["reply"]
    other = asyncio.run(run_turn(g, user_id="jury", session_id="s7", message="recommend me a good restaurant"))
    assert "style assistant" in other["reply"]


def test_a_fashion_question_gets_the_llm_answer():
    class Good(Writer):
        async def ainvoke(self, messages):
            return AIMessage(content="Wash it cold, by hand, and dry it flat. I can also build an outfit with it!")

    g = build_graph(model=Good(), tools=[], rules=True)
    r = asyncio.run(run_turn(g, user_id="jury", session_id="s8", message="how do I wash a wool sweater?"))
    assert r["reply"].startswith("Wash it cold")


def test_follow_ups_reuse_the_last_request():
    m = route_by_rules("Should I buy a navy blazer at 120 TND?", TOOLS)["memory"]
    assert route_by_rules("and in black?", TOOLS, memory=m)["args"] == {"probe_image": "custom:blazer:black", "price_tnd": 120.0}
    assert route_by_rules("cheaper?", TOOLS, memory=m)["args"]["price_tnd"] == 84
    assert route_by_rules("et en beige ?", TOOLS, memory=m)["args"]["probe_image"] == "custom:blazer:beige"
    shop = route_by_rules("Find a white shirt in a shop in Tunis", TOOLS)["memory"]
    assert route_by_rules("in sousse", TOOLS, memory=shop)["args"]["city"] == "Sousse"
    look = route_by_rules("What should I wear tomorrow for work?", TOOLS)["memory"]
    assert route_by_rules("for a wedding instead", TOOLS, memory=look)["name"] == "stylist"
    assert route_by_rules("show my wardrobe", TOOLS, memory=look)["name"] == "wardrobe"  # a new request
    assert route_by_rules("hello", TOOLS, memory=look) is None


def test_memory_across_turns_in_the_graph():
    seen = []
    g = _graph(seen)
    run = lambda m: asyncio.run(run_turn(g, user_id="jury", session_id="s9", message=m))  # noqa: E731
    run("should I buy a navy blazer at 120 TND")
    run("and in white?")
    assert seen[-1] == ("smartbuy", "custom:blazer:white", 120.0)


def test_what_am_i_missing_is_answered_from_the_wardrobe(monkeypatch):
    import shared.wardrobe_gaps as wg

    monkeypatch.setattr(wg, "user_gaps", lambda uid, k=5: [
        {"gap": "white|black t-shirt", "piece": "white t-shirt", "why": "a plain tee goes with every bottom you own", "have": 1}])
    g = build_graph(model=Writer(), tools=[_tool("localshop", lambda **k: None)], rules=True)
    r = asyncio.run(run_turn(g, user_id="jury", session_id="g1", message="what am I missing?"))
    assert "white t-shirt" in r["reply"] and r["cards"][0]["gaps"][0]["piece"] == "white t-shirt"
