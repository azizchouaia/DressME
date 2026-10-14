"""Curated list of Tunisian online shops scraped into the M7 local catalogue.

origin: `local_brand` = Tunisian brand selling its own pieces; `local_retailer` = Tunisian shop or
marketplace reselling other labels. Pieces from known foreign labels become `international_brand`.
city: where the shop/brand is based, checked on the site (store locator, contact page, Shopify meta);
comma-separated for store chains. Left empty for online-only shops or when the site does not say.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Shop:
    key: str
    name: str
    url: str
    platform: str  # key of sources.ADAPTERS
    origin: str = "local_brand"
    city: str = ""
    # default_category: used when no keyword matches;
    # exclude: regex (on folded name + categories) of items to drop;
    # max_products: lower cap than --max-per-shop (e.g. for single-category shops)
    options: dict = field(default_factory=dict)


SHOPS: list[Shop] = [
    # Shopify
    Shop("moudda", "Moudda", "https://moudda.tn", "shopify", origin="local_retailer", city="Tunis"),
    Shop("noon", "NOON Clothing", "https://noonclo.com", "shopify"),
    Shop("manuella", "Manuella", "https://manuella.com.tn", "shopify", city="Tunis"),
    # WooCommerce
    Shop("vog", "VOG", "https://vog.com.tn", "woocommerce", city="Bizerte"),
    Shop("corella", "Corella Store", "https://corella.tn", "woocommerce"),
    Shop("apparel", "Apparel", "https://apparel.tn", "woocommerce"),
    # PrestaShop 1.7+
    Shop("exist", "Exist", "https://www.exist.com.tn", "prestashop"),
    Shop(
        "femodest",
        "FEModest",
        "https://femodest.com",
        "prestashop",
        origin="local_retailer",
        # also sells Islamic books ("Title - Author - Publisher") and prayer beads
        options={
            "exclude": r" - .+ - |livres?|coran|hadith|prophete|spiritualite|jurisprudence|croyance|"
            r"convertis|jeux|famille|tasbih|education"
        },
    ),
    Shop(
        "shoesmall",
        "Shoes Mall",
        "https://shoesmall.tn",
        "prestashop",
        origin="local_retailer",
        city="Sfax",
        options={"default_category": "Chaussures"},
    ),
    # Accessories and shoes chains (added 2026-10-14); cities from their store locator pages
    Shop(
        "strass",
        "Strass Accessoires",
        "https://www.strassaccessoires.com",
        "prestashop",
        city="Tunis, Ariana, Ben Arous, Sousse, Monastir, Sfax, Nabeul",
    ),
    Shop(
        "joliesse",
        "Joliesse",
        "https://joliesse.com.tn/fr",
        "prestashop",
        city="Tunis, Ben Arous, Bizerte, Nabeul, Kélibia, Sousse, Monastir, Sfax, Djerba, Gabès",
    ),
    # PrestaShop 1.6 with a custom theme (HTML product cards)
    Shop("lyoum", "LYOUM", "https://lyoum.tn/fr", "lyoum", city="La Marsa"),
    # schema.org JSON-LD product pages
    Shop(
        "magic",
        "MAGIC",
        "https://magic.tn",
        "jsonld",
        city="Tunis, La Soukra, Bizerte, Nabeul, Menzel Temime, Sousse, Sfax, Béja, Le Kef",
        options={"sitemap": "https://magic.tn/sitemap.xml", "product_pattern": r"/products/"},
    ),
    Shop(
        "unja",
        "UNJA",
        "https://unja.tn",
        "jsonld",
        city="Sfax",
        options={
            "listing_pattern": r'href="(/product-list/[^"]+)"',
            "product_pattern": r'href="(/product/[^"]+)"',
        },
    ),
    # Custom JSON API
    Shop("ha", "HA", "https://ha.com.tn", "ha", options={"sections": ["femme", "homme"]}),
]

# Shops from the source list that are not scraped, and why (kept for the README / report).
SKIPPED: dict[str, str] = {
    "Ad. Mall (admall.tn)": "server-rendered marketplace, no product feed; to add with an HTML parser",
    "boutique.tn": "multi-vendor storefront on sub-domains; to add with an HTML parser",
    "Hawwini": "price comparator, used only to discover shop URLs",
    "Lofa (lofa.tn)": "demo catalogue (14 products with stock photos)",
    "Celina Fashion": "showcase site, no online catalogue",
    "D'Stock (dstock.com.tn)": "Angular SSR pages without structured data; to add with an HTML parser",
    "Dabchy": "second-hand marketplace (user listings, not shops)",
    "Fripup": "site down (HTTP 520)",
    "MODECO": "site unreachable",
    "Spadri": "site unreachable",
    "Goat Sneakers": "no reachable website found",
    "JENNAH Boutique": "French shop (prices in EUR, based in Pantin)",
    "Ayada Boutique": "French shop (redirects to ayada.fr, prices in EUR)",
    "Scarpa Store": "resells foreign labels only (Adidas, Saucony, Givenchy...)",
    "Sneakers Tunisie": "resells foreign labels only (Nike, UGG, Moncler...)",
    "Sneakers Outlet": "resells foreign labels only (Adidas, New Balance, UGG...)",
    "SKILA (skila.co)": "showcase site: scarf galleries without prices or product pages",
    "Shoes Center (shoescenter.tn)": "parked domain (no shop); shoescenter.com.tn has an invalid certificate",
    "Chaussures Pitillos": "Spanish brand (Arnedo, calzadospitillos.com): not a local label",
    "HK-STORE Accessoires": "no website found (in-store / social media only)",
    "GAYA accessoire": "no website found (gaya.tn answers 503)",
    "The Queen Accessories (Palmarium)": "physical shop, no website found",
    "Azar Shoes (Tunisia Mall)": "physical shop, no website found",
}
