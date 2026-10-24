"""Fixed M7 answer in the real contract shape, for other modules' offline tests (no data, no model).

Same signature as service.search (sync here). Data copied from a real search of the catalogue.
"""


def search(req: dict) -> dict:
    return {
        "results": [
            {
                "shop": "Manuella",
                "area": "Tunis",
                "item": "Basket à plateforme femme",
                "price_tnd": 69.3,
                "match": 0.87,
                "product_id": "prd_2b7db627f3",
                "category": "shoes",
                "subcategory": "sneakers",
                "color": "white",
                "size": "36, 37, 38, 39, 40, 41",
                "image_url": "https://cdn.shopify.com/s/files/1/0718/3165/0453/files/basket-plateforme.jpg",
                "image_path": None,
                "product_url": "https://manuella.com.tn/products/basket-a-plateforme-femme",
                "shop_url": "https://manuella.com.tn",
                "origin_type": "local_brand",
                "available": True,
                "reasons": ["Baskets", "Couleur : blanc", "69.3 TND (budget 80 TND)", "Boutique à Tunis"],
            }
        ],
        "parsed": {
            "category": "shoes",
            "subcategory": "sneakers",
            "color": "white",
            "max_price_tnd": 80.0,
            "city": "Tunis",
            "governorate": "Tunis",
            "terms": ["basket", "blanche"],
            "prompt_en": "a photo of white sneakers",
        },
        "total_matches": 1,
        "note": "Réponse fixe (mock M7) : catalogue local non installé sur cette machine.",
    }


def shops() -> list[dict]:
    return [
        {
            "shop": "Manuella",
            "city": "Tunis",
            "shop_url": "https://manuella.com.tn",
            "origin_type": "local_brand",
            "products": 1,
        }
    ]


def outfits(req: dict) -> dict:
    """Fixed OutfitsOutput, so the app and the other BOs can code against /m07/outfits offline."""
    return {
        "product_id": req.get("product_id", "prd_demo"),
        "piece": "Chemise en lin blanche · Boutique démo · 79 TND",
        "outfits": [
            {
                "pieces": [
                    {
                        "item_id": req.get("product_id", "prd_demo"),
                        "label": "Chemise en lin blanche",
                        "source": "shop",
                    },
                    {"item_id": "itm_jean01", "label": "jean (bleu)", "source": "wardrobe"},
                    {"item_id": "itm_bask01", "label": "baskets (blanc)", "source": "wardrobe"},
                ],
                "score": 0.8,
                "reasons": [],
            }
        ],
        "goes_with": ["jean (bleu)", "baskets (blanc)"],
        "why": [
            "Marque tunisienne : Boutique démo",
            "79 TND",
            "Va avec ta garde-robe : jean (bleu), baskets (blanc)",
        ],
        "sources": {"m1": "mock", "m2": "mock"},
    }


def local_pieces(req: dict) -> dict:
    """Fixed LocalPiecesOutput, so BO1 and the app can code against /m07/local-pieces offline."""
    product = search({"query": "baskets"})["results"][0]
    return {
        "outfit": ["jean (bleu)", "chemise (blanc)"],
        "suggestions": [
            {
                "action": "complete",
                "slot": "shoes",
                "replaces": None,
                "product": product,
                "score": 0.8,
                "reasons": ["Complète ta tenue : chaussures", "Avec : jean (bleu), chemise (blanc)"],
            }
        ],
        "sources": {"m1": "mock", "m2": "mock"},
    }
