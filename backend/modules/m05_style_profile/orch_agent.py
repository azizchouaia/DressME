"""M5 entry for the orchestrator (BO8): the REAL style profile of the user (Bali's M5), no mock.

- a question in words ("what is my style?", "more classic") -> M5's own style coach (LangGraph + local LLM);
- no message, or the coach / LLM unavailable -> the learnt profile itself (style mix, top styles, onboarded).
"""

from shared.agent_card import AgentCall, AgentResult, BaseAgent, describe

from .identity import CARD


class Agent(BaseAgent[AgentCall, AgentResult]):
    name = CARD["name"]
    description = describe(CARD)
    input_model = AgentCall
    output_model = AgentResult

    async def run(self, inp: AgentCall) -> AgentResult:
        from . import service

        body: dict = (await service.profile_envelope({"user_id": inp.user_id}))["result"]
        message = inp.message or str(inp.payload.get("message") or "")
        if message and body.get("onboarded"):
            try:
                from .agent import graph
                from .contract import AgentChatRequest

                chat = await graph.chat(AgentChatRequest(user_id=inp.user_id, message=message, thread_id=inp.session_id[:64]))
                body = {**body, "coach": chat.model_dump(mode="json") if hasattr(chat, "model_dump") else chat}
            except Exception as e:  # noqa: BLE001 - the coach needs the local LLM: answer with the profile
                body = {**body, "coach_unavailable": f"{type(e).__name__}: {e}"}
        if not body.get("onboarded"):
            body = {**body, "next": "swipe the 10 onboarding cards first (app: My style)"}
        return AgentResult(agent=CARD["name"], result=body, next_actions=list(CARD.get("handoff") or []), mocked=False)
