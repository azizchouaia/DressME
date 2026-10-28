# Orchestrator — owner: BO8

LangGraph graph for the DressMe chat. The planner picks one agent. The agent decides. This graph asks the agent's question, follows `next_actions`, and words the reply.

```
begin -> planner --(tool call)--> prepare_tools -> tools -> after_tool
after_tool: question      -> ask_user -> END
            next_actions  -> planner          (until 3 tool calls)
            else          -> writer   -> END
```

`thread_id` is the `session_id` passed to every agent. Memory is `MemorySaver` for now.

Run the loop tests from `backend/`:

```
.venv\Scripts\python.exe -m pytest orchestrator/tests -q
```

`run_turn` in `graph.py` is the local entry. `backend/api/routes/chat.py` is still the gateway stub.

Who does what, and when the planner should call them, is in [AGENTS.md](AGENTS.md).
