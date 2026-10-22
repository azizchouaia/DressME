import uuid
from pathlib import Path

import yaml

from shared.base_agent import AgentError, BaseAgent

from .contract import PipelineStep, ShareCardInput, ShareCardOutput
from .pipeline import caption, caption_llm, layout, links, metrics, palette
from .store import MemoryShareStore, ShareStore

CONFIG = yaml.safe_load((Path(__file__).parent / "config.yaml").read_text())

HEADER_H = 330  # eyebrow + 2-line title + subtitle
QR_BAND = 210  # room kept above the footer for the QR code
FOOTER_H = 150
STAT_TILE_H = 180


class ShareAgent(BaseAgent[ShareCardInput, ShareCardOutput]):
    name = "share"
    description = (
        "Create a shareable image card (outfit, builder board, try-on look, monthly recap, challenge entry, "
        "trip lookbook, style timeline, poll) with a referral link, ready for Instagram / WhatsApp."
    )
    input_model = ShareCardInput
    output_model = ShareCardOutput
    is_async_job = False

    def __init__(self, config: dict | None = None, store: ShareStore | None = None):
        super().__init__(config or CONFIG)
        self.store: ShareStore = store or MemoryShareStore(use_s3=self.config.get("storage") == "s3")

    async def run(self, inp: ShareCardInput) -> ShareCardOutput:
        if not inp.items and not inp.stats:
            raise AgentError("A card needs at least one item or one stat.")
        from .pipeline import render  # Pillow is imported only when a card is drawn

        W, H = self.config["formats"][inp.format]
        margin = 72
        content = (margin, HEADER_H, W - 2 * margin, H - HEADER_H - FOOTER_H - (QR_BAND if inp.qr else 0))

        # garments area leaves room for the stat tiles at the bottom
        g_area = content
        if inp.items and inp.stats:
            rows = (len(inp.stats) + 1) // 2
            g_area = (content[0], content[1], content[2], content[3] - rows * (STAT_TILE_H + 20) - 20)

        steps = [
            PipelineStep(
                stage="input",
                method="data",
                name="Card request",
                detail=f"kind={inp.kind}, {len(inp.items)} item(s), {len(inp.stats)} stat(s), {inp.format}",
            )
        ]
        items = [it.model_dump(mode="json") for it in inp.items]

        # ML · K-means: dominant colour of each cutout that came without a colour from M1
        learned = 0
        for it in items:
            if it.get("image") and not it.get("color_hex"):
                img = render.load_image(it["image"], self.config.get("image_fetch_timeout_s", 4))
                if img is not None:
                    from .pipeline import colors_ml

                    cols = colors_ml.dominant_colors(img)
                    if cols:
                        it["color_hex"] = cols[0][0]
                        learned += 1
        steps.append(
            PipelineStep(
                stage="code",
                method="ML",
                name="K-means colour extraction",
                detail=(
                    f"dominant colour learned from {learned} cutout(s)"
                    if learned
                    else "colours already provided by M1 (K-means runs on cutouts without colour)"
                ),
            )
        )

        avatar_area = None
        if inp.kind == "tryon":  # avatar (M9) on the left, the outfit pieces in a column on the right
            ax, ay, aw, ah = g_area
            split = int(aw * 0.6)
            avatar_area = (ax, ay, split - 24, ah)
            g_area = (ax + split, ay, aw - split, ah)
        boxes = layout.run(items, g_area, weights=self.config.get("row_weights"))
        steps.append(
            PipelineStep(
                stage="code",
                method="if/else",
                name="Flat-lay layout",
                detail=f"{len(boxes)} item(s) placed by body zone (upper / lower / feet), no overlap",
            )
        )
        pal = palette.run([it.get("color_hex") for it in items])
        steps.append(
            PipelineStep(
                stage="code",
                method="if/else",
                name="Palette rules",
                detail=f"background {pal.background}, text {pal.text} (light clothes → dark card, WCAG 4.5)",
            )
        )

        code = links.short_code(inp.user_id, inp.source_id)
        url = links.share_url(self.config["public_base_url"], code)
        stats = [(s.label, s.value) for s in inp.stats]
        png = render.run(
            kind=inp.kind,
            size=(W, H),
            palette=pal,
            boxes=boxes,
            items={it["item_id"]: it for it in items},
            title=inp.title,
            subtitle=inp.subtitle,
            stats=stats,
            footer=url.split("://", 1)[-1] if inp.watermark else None,
            content_area=content,
            avatar=(inp.avatar_image or "", avatar_area) if avatar_area else None,
            qr_url=f"{url}?ch=qr" if inp.qr else None,
            font_path=self.config.get("font_path"),
            timeout=self.config.get("image_fetch_timeout_s", 4),
        )

        labels = [it.label or it.category.value for it in inp.items]
        brands = [it.brand for it in inp.items if it.brand]
        steps.append(
            PipelineStep(
                stage="code",
                method="if/else",
                name="Referral link",
                detail=f"base62 code {code} → {url}"
                + (" · QR code drawn on the card (?ch=qr)" if inp.qr else ""),
            )
        )
        gen = caption_llm.write(inp.kind, labels, brands, inp.title, inp.subtitle, stats, inp.language)
        steps.append(
            PipelineStep(
                stage="code",
                method="LLM · RAG",
                name="Retrieve caption guidelines",
                detail=", ".join(f"{d['id']} ({d['score']})" for d in gen["retrieved"]) or "no match",
            )
        )
        steps.append(
            PipelineStep(
                stage="code",
                method="LLM · PE",
                name="Caption prompt",
                detail=(
                    "LLM wrote the caption"
                    if gen["source"] == "llm"
                    else "no LLM configured in infra/.env → template caption (if/else fallback)"
                ),
            )
        )
        text, source = (inp.caption, "user") if inp.caption else (gen["caption"], gen["source"])
        alt = caption.alt_text(
            inp.kind, [(it.label or it.item_id, it.category.value) for it in inp.items], inp.title
        )

        card_id = f"card_{uuid.uuid4().hex[:12]}"
        meta = {
            "card_id": card_id,
            "user_id": inp.user_id,
            "kind": inp.kind,
            "short_code": code,
            "source_id": inp.source_id,
            "caption": text,
            "share_url": url,
            "channel_links": links.channel_links(url, text),
            "width": W,
            "height": H,
            "alt_text": alt,
            "background_hex": pal.background,
            "item_ids": [it.item_id for it in inp.items],
        }
        image_url = self.store.save_card(meta, png)
        steps.append(
            PipelineStep(
                stage="output",
                method="data",
                name="Share card",
                detail=f"PNG {W}×{H}, caption, link, alt text",
            )
        )
        return ShareCardOutput(
            card_id=card_id,
            short_code=code,
            image_url=image_url,
            share_url=url,
            channel_links=meta["channel_links"],
            width=W,
            height=H,
            caption=text,
            alt_text=alt,
            background_hex=pal.background,
            caption_source=source,
            pipeline=steps,
            retrieved=gen["retrieved"],
            prompt=gen["prompt"],
        )

    # --- referral attribution (called by the API, not by the orchestrator) ---
    @staticmethod
    def _channel(ch: str | None) -> str:
        """if/else: unknown or missing channel tags count as 'direct'."""
        return ch if ch in links.CHANNELS else "direct"

    def open_link(self, code: str, channel: str | None = None) -> dict:
        card = self.store.find_by_code(code)
        if card is None:
            raise AgentError(f"Unknown share code {code}")
        self.store.add_open(code, self._channel(channel))
        return card

    def attribute_signup(self, code: str, new_user_id: str, channel: str | None = None) -> None:
        if self.store.find_by_code(code) is None:
            raise AgentError(f"Unknown share code {code}")
        self.store.add_signup(code, new_user_id, self._channel(channel) if channel else None)

    def metrics(self, user_id: str | None = None) -> metrics.ShareMetrics:
        return metrics.compute(*self.store.events(user_id))

    def ambassadors(self, top: int = 10) -> list[dict]:
        return metrics.ambassadors(*self.store.events(None), top=top)
