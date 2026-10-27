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
