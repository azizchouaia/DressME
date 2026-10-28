"""Terminal test: python -m bo.bo5_purchase.cli --demo"""

import argparse
import asyncio
import json

from modules.m06_smartbuy.agent import SmartBuyAgent

ICON = {"buy": "BUY  ", "think": "THINK", "skip": "SKIP "}


def show(name, out):
    print(f"\n[{ICON[out['verdict']]}] {name}  score {out['score']}/100")
    print("   " + out["explanation"])
    print("   breakdown:", out["breakdown"])
    if out["similar_items"]:
        print("   similar:", ", ".join(f"{s['label']} ({s['similarity']})" for s in out["similar_items"]))
    if out["size_advice"]:
        print("   size:", out["size_advice"]["note"])
    for l in out["buy_links"]:
        print(f"   buy: {l['shop']} - {l['item']} {l['price_tnd']} TND  code {l['promo_code']}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--demo", action="store_true")
    p.add_argument("--image")
    p.add_argument("--price", type=float)
    p.add_argument("--brand")
    p.add_argument("--chest", type=float)
    p.add_argument("--waist", type=float)
    p.add_argument("--json", action="store_true")
    a = p.parse_args()
    agent = SmartBuyAgent()
    if a.demo:
        runs = [("cand_white_shirt", 79, "Medina Atelier"), ("cand_navy_shirt", 69, None),
                ("cand_red_dress", 180, None), ("cand_grey_jeans", 95, "Carthage Denim Co.")]
        for img, price, brand in runs:
            out = asyncio.run(agent({"user_id": "usr_demo", "probe_image": img, "price_tnd": price,
                                     "shop_brand": brand, "body": {"chest_cm": 98, "waist_cm": 84}}))
            show(img, out)
        return
    body = {"chest_cm": a.chest, "waist_cm": a.waist} if (a.chest or a.waist) else None
    out = asyncio.run(agent({"user_id": "usr_demo", "probe_image": a.image, "price_tnd": a.price,
                             "shop_brand": a.brand, "body": body}))
    print(json.dumps(out, indent=2, ensure_ascii=False)) if a.json else show(a.image, out)


if __name__ == "__main__":
    main()
