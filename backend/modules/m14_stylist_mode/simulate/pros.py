"""Demo professionals: fictional stylists, boutique accounts for a few M7 shops, clients who accepted.

    cd backend && python -m modules.m14_stylist_mode.simulate.pros [--reset]

Names are fictional and marked "(demo)"; boutique accounts are unverified demo accounts of catalogue
shops, so the hand-off and the boutique dashboard can be shown end to end.
"""

import argparse
import asyncio
import json

from .. import paths, service, store

STYLISTS = [
    ("Amel (demo)", "Tunis", ["mariage", "soirée", "traditionnel"], ["fr", "darija"]),
    ("Yasmine (demo)", "La Marsa", ["bureau", "minimaliste", "entretien"], ["fr", "en"]),
    ("Sami (demo)", "Tunis", ["homme", "costume", "mariage"], ["fr", "darija"]),
    ("Ines (demo)", "Sousse", ["mariage", "henna", "fiançailles", "traditionnel"], ["fr", "darija", "ar"]),
    ("Mehdi (demo)", "Sfax", ["streetwear", "baskets", "homme"], ["fr", "darija"]),
    ("Rania (demo)", "Ariana", ["hijab", "modest", "bureau"], ["fr", "ar", "darija"]),
    ("Leila (demo)", "Monastir", ["soirée", "robe", "mariage"], ["fr", "en"]),
    ("Karim (demo)", "Nabeul", ["sport", "casual", "homme"], ["fr", "en", "darija"]),
]
BOUTIQUES = [("Manuella", "Tunis"), ("Ms. Marion", "Tunis"), ("Cravate", "Tunis"), ("Joliesse", "Sousse")]
CLIENTS = ["usr_042", "usr_043", "usr_044"]


async def seed(reset: bool = False) -> dict:
    if reset:
        for name in ("pros", "links", "reviews", "looks", "handoffs"):
            (paths.data_dir() / f"{name}.json").unlink(missing_ok=True)
    made = {"stylists": 0, "boutiques": 0, "links": 0}
    for name, city, specialities, languages in STYLISTS:
        if not store.pros.find(name=name):
            await service.create_pro(
                {
                    "type": "stylist",
                    "name": name,
                    "city": city,
                    "shop": None,
                    "specialities": specialities,
                    "languages": languages,
                    "bio": None,
                    "style_vector": None,
                }
            )
            made["stylists"] += 1
    for shop, city in BOUTIQUES:
        if not store.pros.find(type="boutique", shop=shop):
            try:
                await service.create_pro(
                    {
                        "type": "boutique",
                        "name": f"{shop} (demo)",
                        "city": city,
                        "shop": shop,
                        "specialities": [],
                        "languages": ["fr"],
                        "bio": None,
                        "style_vector": None,
                    }
                )
                made["boutiques"] += 1
            except ValueError as exc:  # shop not in this catalogue
                print("skipped:", exc)
    # Demo loyalty codes (Backup 2), marked DEMO: no real agreement with these shops.
    for pro in store.pros.find(type="boutique"):
        if not pro.get("loyalty"):
            slug = "".join(ch for ch in pro["shop"].upper() if ch.isalnum())[:12]
            service.update_pro(
                pro["pro_id"],
                {
                    "loyalty": {
                        "code": f"{slug}-DEMO10",
                        "discount_pct": 10,
                        "conditions": "Démo : code fictif",
                    }
                },
            )
    pros = list(store.pros.all().values())  # every demo pro has the demo clients
    for pro in pros:
        for client in CLIENTS:
            link = service.invite({"pro_id": pro["pro_id"], "client_id": client, "message": "Démo"})
            if link["status"] == "invited":
                service.consent(link["link_id"], client, True)
                made["links"] += 1
    return made | {"pros": {p["name"]: p["pro_id"] for p in store.pros.all().values()}}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--reset", action="store_true", help="delete M14's demo data first")
    args = parser.parse_args(argv)
    print(json.dumps(asyncio.run(seed(args.reset)), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
