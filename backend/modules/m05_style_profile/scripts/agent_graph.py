"""Exports the style coach pipeline (LangGraph) for the slides.

    cd backend
    python -m modules.m05_style_profile.scripts.agent_graph            # -> agent/pipeline.mmd (+ .png)

The .mmd (Mermaid) is always written; the PNG is rendered through mermaid.ink, so it needs internet.
Paste the .mmd into https://mermaid.live to edit or export it by hand.
"""

from pathlib import Path

from modules.m05_style_profile.agent.graph import build_graph

OUT = Path(__file__).resolve().parents[1] / "agent"


def main() -> None:
    g = build_graph("demo").get_graph()
    (OUT / "pipeline.mmd").write_text(g.draw_mermaid(), encoding="utf-8")
    print(f"written {OUT / 'pipeline.mmd'}")
    try:
        (OUT / "pipeline.png").write_bytes(g.draw_mermaid_png())
        print(f"written {OUT / 'pipeline.png'}")
    except Exception as e:  # offline, mermaid.ink down
        print(f"PNG skipped ({e}); open pipeline.mmd in https://mermaid.live")


if __name__ == "__main__":
    main()
