"""One adapter per e-commerce platform. Each returns RawProduct records with prices in TND."""

import html
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit

import requests

from .client import XHR_JSON, Disallowed, Http
from .normalize import clean_text, fold
from .shops import Shop

COLOR_OPTIONS = ("couleur", "color", "colour", "coloris", "teinte")
SIZE_OPTIONS = ("taille", "size", "pointure")


@dataclass
class RawProduct:
    name: str
    product_url: str
    price_tnd: float | None
    image_url: str = ""
    category_texts: list[str] = field(default_factory=list)  # product type, categories, breadcrumb
    tags: str = ""
    colors: list[str] = field(default_factory=list)
    sizes: list[str] = field(default_factory=list)
    available: bool = True
    brand: str = ""
    extra_text: str = ""  # short description, used as a last resort for the colour
    enrich: Callable[["RawProduct"], None] | None = None  # detail-page fetch, run only on selected products


def _is_option(name: str, kinds: tuple[str, ...]) -> bool:
    folded = fold(name).replace("pa_", "")
    return any(kind in folded for kind in kinds)


def _price(value) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = re.sub(r"[^\d,\.]", "", str(value))
    if "," in text and "." in text:
        text = (
            text.replace(",", "")
            if text.rfind(".") > text.rfind(",")
            else text.replace(".", "").replace(",", ".")
        )
    else:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


# --- Shopify: public /products.json ---------------------------------------------------------------


def shopify(shop: Shop, http: Http, max_raw: int) -> list[RawProduct]:
    base = shop.url.rstrip("/")
    out: list[RawProduct] = []
    page = 1
    while len(out) < max_raw:
        products = (
            http.json(f"{base}/products.json", params={"limit": 250, "page": page}).get("products") or []
        )
        if not products:
            break
        for p in products:
            options = p.get("options") or []
            color_pos = next(
                (o["position"] for o in options if _is_option(o.get("name", ""), COLOR_OPTIONS)), None
            )
            size_pos = next(
                (o["position"] for o in options if _is_option(o.get("name", ""), SIZE_OPTIONS)), None
            )
            variants = p.get("variants") or []
            in_stock = [v for v in variants if v.get("available")]
            pool = in_stock or variants
            prices = [x for x in (_price(v.get("price")) for v in pool) if x]
            tags = p.get("tags") or []
            out.append(
                RawProduct(
                    name=clean_text(p.get("title", "")),
                    product_url=f"{base}/products/{p['handle']}",
                    price_tnd=min(prices) if prices else None,
                    image_url=((p.get("images") or [{}])[0]).get("src", ""),
                    category_texts=[p.get("product_type") or ""],
                    tags=" ".join(tags) if isinstance(tags, list) else str(tags),
                    colors=[v.get(f"option{color_pos}") or "" for v in pool] if color_pos else [],
                    sizes=[v.get(f"option{size_pos}") or "" for v in in_stock] if size_pos else [],
                    available=bool(in_stock),
                    brand=p.get("vendor") or "",
                    extra_text=(p.get("body_html") or "")[:600],
                )
            )
        page += 1
    return out


# --- WooCommerce: public Store API -----------------------------------------------------------------


def woocommerce(shop: Shop, http: Http, max_raw: int) -> list[RawProduct]:
    base = shop.url.rstrip("/") + "/"
    out: list[RawProduct] = []
    page = 1
    while len(out) < max_raw:
        try:
            products = http.json(
                base, params={"rest_route": "/wc/store/v1/products", "per_page": 100, "page": page}
            )
        except requests.HTTPError:
            break  # past the last page
        if not products:
            break
        for p in products:
            prices = p.get("prices") or {}
            if prices.get("currency_code") not in (None, "TND"):
                continue
            minor = int(prices.get("currency_minor_unit") or 0)
            raw_price = prices.get("price") or prices.get("regular_price")
            attributes = p.get("attributes") or []
            out.append(
                RawProduct(
                    name=clean_text(p.get("name", "")),
                    product_url=p.get("permalink", ""),
                    price_tnd=int(raw_price) / 10**minor if raw_price not in (None, "") else None,
                    image_url=((p.get("images") or [{}])[0]).get("src", ""),
                    category_texts=[clean_text(c.get("name", "")) for c in p.get("categories") or []],
                    tags=" ".join(clean_text(t.get("name", "")) for t in p.get("tags") or []),
                    colors=_woo_terms(attributes, COLOR_OPTIONS),
                    sizes=_woo_terms(attributes, SIZE_OPTIONS),
                    available=bool(p.get("is_in_stock", True)),
                    brand=" ".join(clean_text(b.get("name", "")) for b in p.get("brands") or []),
                    extra_text=(p.get("short_description") or "")[:600],
                )
            )
        page += 1
    return out


def _woo_terms(attributes: list[dict], kinds: tuple[str, ...]) -> list[str]:
    return [
        t.get("name", "")
        for a in attributes
        if _is_option(a.get("name", ""), kinds)
        for t in a.get("terms") or []
    ]


# --- PrestaShop 1.7+/8: category listings return JSON when asked via XHR ---------------------------


def prestashop(shop: Shop, http: Http, max_raw: int) -> list[RawProduct]:
    base = shop.url.rstrip("/")
    home = http.text(base + "/")
    category_urls = [base + "/2-accueil"]
    for url in re.findall(rf'href="({re.escape(base)}/\d+-[a-z0-9\-]+)"', home):
        if url not in category_urls:
            category_urls.append(url)

    found: dict[str, RawProduct] = {}
    for category_url in category_urls:
        category_hint = re.sub(r"^\d+-+", "", category_url.rsplit("/", 1)[-1]).replace("-", " ")
        page = 1
        while len(found) < max_raw:
            try:
                data = http.json(category_url, params={"page": page, "resultsPerPage": 48}, headers=XHR_JSON)
            except (requests.HTTPError, ValueError, Disallowed):
                break
            products = data.get("products") or []
            for p in products:
                pid = str(p.get("id_product"))
                if pid in found:
                    # Listed again under a more specific category ("femme" first, then "sandales"):
                    # keep that hint, it is the only type information for names like "Cinzia Noir Daim".
                    if category_hint not in found[pid].category_texts:
                        found[pid].category_texts.append(category_hint)
                    continue
                cover = p.get("cover") or {}
                image = (cover.get("large") or {}).get("url") or (
                    (cover.get("bySize") or {}).get("large_default") or {}
                ).get("url", "")
                found[pid] = RawProduct(
                    name=clean_text(p.get("name", "")),
                    product_url=(p.get("canonical_url") or p.get("url") or "").split("#")[0],
                    price_tnd=_price(p.get("price_amount")) or _price(p.get("price")),
                    image_url=image,
                    category_texts=[p.get("category_name") or "", category_hint],
                    colors=[
                        v.get("name", "") for v in p.get("main_variants") or [] if v.get("type") == "color"
                    ],
                    brand=p.get("manufacturer_name") or "",
                    extra_text=(p.get("description_short") or "")[:600],
                    enrich=lambda raw, h=http: _prestashop_details(raw, h),
                )
            pages = (data.get("pagination") or {}).get("pages_count") or 1
            if not products or page >= pages:
                break
            page += 1
        if len(found) >= max_raw:
            break
    return list(found.values())


def _prestashop_details(raw: RawProduct, http: Http) -> None:
    """Sizes and stock are only on the product page (variant selector + data-product JSON)."""
    try:
        page = http.text(raw.product_url)
    except (requests.RequestException, Disallowed):
        return
    sizes: list[str] = []
    # Standard theme: <label class="control-label">Taille</label>; Creative Elements theme:
    # <span class="ce-product-variants__label">Pointure</span>
    label_re = re.compile(r'class="(?:control-label|ce-product-variants__label)"[^>]*>\s*([^<]+?)\s*<')
    labels = list(label_re.finditer(page))
    for i, m in enumerate(labels):
        if not _is_option(m.group(1), SIZE_OPTIONS):
            continue
        end = labels[i + 1].start() if i + 1 < len(labels) else m.end() + 30000
        chunk = page[m.end() : min(end, m.end() + 30000)]
        sizes += (
            re.findall(r"<option[^>]*>\s*([^<]+?)\s*</option>", chunk)
            or re.findall(r'<span class="radio-label[^"]*">\s*([^<]+?)\s*</span>', chunk)
            or re.findall(r'<span class="ce-product-variants__option">\s*([^<]+?)\s*</span>', chunk)
            or re.findall(r'title="([^"]+)"', chunk)
        )
    raw.sizes = sizes
    m = re.search(r'data-product="([^"]+)"', page)
    if m:
        try:
            details = json.loads(html.unescape(m.group(1)))
            if isinstance(details, dict):
                raw.available = details.get("availability") != "unavailable"
        except ValueError:
            pass


# --- Generic: product pages with schema.org Product JSON-LD ---------------------------------------


def jsonld(shop: Shop, http: Http, max_raw: int) -> list[RawProduct]:
    base = shop.url.rstrip("/")
    opts = shop.options
    urls: list[str] = []
    if "sitemap" in opts:
        locs = re.findall(r"<loc>\s*([^<]+?)\s*</loc>", http.text(opts["sitemap"]))
        urls = [u for u in locs if re.search(opts["product_pattern"], u)]
    else:
        home = http.text(base + "/")
        listings = list(dict.fromkeys(re.findall(opts["listing_pattern"], home)))
        for listing in listings:
            try:
                page = http.text(urljoin(base + "/", listing))
            except (requests.RequestException, Disallowed):
                continue
            for link in re.findall(opts["product_pattern"], page):
                url = urljoin(base + "/", link)
                if url not in urls:
                    urls.append(url)

    out: list[RawProduct] = []
    for url in urls[:max_raw]:
        try:
            page = http.text(url)
        except (requests.RequestException, Disallowed):
            continue
        product, crumbs = _ld_product(page)
        if not product:
            continue
        offers = product.get("offers") or {}
        offers = offers if isinstance(offers, list) else [offers]
        currency = next((o.get("priceCurrency") for o in offers if o.get("priceCurrency")), "TND")
        if currency != "TND":
            continue
        prices = [x for o in offers for x in (_price(o.get("price")), _price(o.get("lowPrice"))) if x]
        image = product.get("image") or ""
        if isinstance(image, list):
            image = image[0] if image else ""
        if isinstance(image, dict):
            image = image.get("url", "")
        brand = product.get("brand") or ""
        path_hint = " ".join(urlsplit(url).path.strip("/").split("/")[:-1]).replace("-", " ")
        out.append(
            RawProduct(
                name=clean_text(product.get("name", "")),
                product_url=url,
                price_tnd=min(prices) if prices else None,
                image_url=image,
                category_texts=[str(product.get("category") or ""), " ".join(crumbs), path_hint],
                colors=[product["color"]] if isinstance(product.get("color"), str) else [],
                sizes=_page_sizes(page)
                or ([product["size"]] if isinstance(product.get("size"), str) else []),
                available=not any("OutOfStock" in str(o.get("availability", "")) for o in offers),
                brand=brand.get("name", "") if isinstance(brand, dict) else str(brand),
                extra_text=str(product.get("description") or "")[:600],
            )
        )
    return out


def _ld_product(page: str) -> tuple[dict | None, list[str]]:
    product, crumbs = None, []
    for block in re.findall(r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", page, re.S):
        try:
            data = json.loads(block.strip(), strict=False)
        except ValueError:
            continue
        nodes = data if isinstance(data, list) else data.get("@graph", [data])
        for node in nodes:
            if not isinstance(node, dict):
                continue
            kind = node.get("@type")
            kinds = kind if isinstance(kind, list) else [kind]
            if "Product" in kinds and product is None:
                product = node
            if "BreadcrumbList" in kinds:
                crumbs = [
                    str(
                        (i.get("item") or {}).get("name")
                        if isinstance(i.get("item"), dict)
                        else i.get("name") or ""
                    )
                    for i in node.get("itemListElement") or []
                ]
    return product, crumbs


def _page_sizes(page: str) -> list[str]:
    """Best-effort size buttons on SPA product pages (Nuxt/TikTak/Magic): short labels like S, M, 38..."""
    block = re.search(r"(?:Tailles?|Pointures?|Size)\s*:?\s*</[^>]+>(.{0,4000})", page, re.S)
    if not block:
        return []
    labels = re.findall(
        r">\s*(XXS|XS|S|M|L|XL|XXL|XXXL|[2-5]XL|\d{2}(?:[\.,]5)?|T[0-6]|Taille unique)\s*<", block.group(1)
    )
    return labels


# --- HA (ha.com.tn): Vue SPA backed by a JSON API --------------------------------------------------


def ha(shop: Shop, http: Http, max_raw: int) -> list[RawProduct]:
    base = shop.url.rstrip("/")
    out: list[RawProduct] = []
    sections = shop.options.get("sections", ["femme", "homme"])
    per_section = max_raw // len(sections) + 1
    for section in sections:
        page, taken = 1, 0
        while taken < per_section:
            try:
                data = http.json(
                    f"{base}/api/items/list",
                    params={"page": page, "pageSize": 48, "selectedSection": section, "requestTimestamp": 1},
                )
            except requests.HTTPError:
                break
            items = data.get("list") or []
            for item in items:
                variants = [v for vs in (item.get("sizes") or {}).values() for v in vs]
                in_stock_sizes = [
                    size
                    for size, vs in (item.get("sizes") or {}).items()
                    if any(v.get("stock", 0) > 0 for v in vs)
                ]
                colors = [(item.get("color") or {}).get("name", "")] + [
                    (v.get("color") or {}).get("name", "") for v in variants
                ]
                url_path = item.get("url") or ""
                out.append(
                    RawProduct(
                        name=clean_text(item.get("title", "")),
                        product_url=f"{base}/catalogue{url_path}",
                        price_tnd=_price(item.get("priceDiscounted") or item.get("price")),
                        image_url=f"{base}/api/image/get/{item['image']}" if item.get("image") else "",
                        category_texts=[
                            (item.get("subGroup") or {}).get("name", ""),
                            url_path.replace("/", " ").replace("-", " "),
                        ],
                        colors=[c for c in colors if c],
                        sizes=in_stock_sizes,
                        available=bool(in_stock_sizes),
                        brand=(item.get("brand") or {}).get("name", "")
                        if isinstance(item.get("brand"), dict)
                        else "",
                        extra_text=item.get("description") or "",
                    )
                )
                taken += 1
            if not items or page >= (data.get("maxPagesCount") or 1):
                break
            page += 1
    return out


# --- LYOUM (lyoum.tn): PrestaShop 1.6 custom theme, everything is on the category product cards ---


def lyoum(shop: Shop, http: Http, max_raw: int) -> list[RawProduct]:
    base = shop.url.rstrip("/")
    home = http.text(base + "/")
    category_urls = list(dict.fromkeys(re.findall(rf'href="({re.escape(base)}/\d+-[a-z0-9\-]+)"', home)))
    found: dict[str, RawProduct] = {}
    for category_url in category_urls:
        category_hint = re.sub(r"^\d+-+", "", category_url.rsplit("/", 1)[-1]).replace("-", " ")
        try:
            page = http.text(category_url)
        except (requests.RequestException, Disallowed):
            continue
        for card in page.split('<li class="best-img"')[1:]:
            card = card.split('class="quick-view-wrapper"')[0]
            link = re.search(r'href="([^"#]+\.html)', card)
            name = re.search(r"<h4>\s*(.*?)\s*</h4>", card, re.S)
            if not link or not name or link.group(1) in found:
                continue
            image = re.search(r'<img src="([^"]+)"', card)
            price = re.search(r'itemprop="price"[^>]*>\s*([^<]+)<', card)
            color = re.search(r"<p class='color'>\s*([^<]+?)\s*</p>", card)
            sizes = re.findall(r"<li class='\s*found\s*'>\s*([^<]+?)\s*</li>", card)
            url_category = link.group(1).split(base + "/", 1)[-1].split("/")[0]
            found[link.group(1)] = RawProduct(
                name=clean_text(name.group(1)),
                product_url=link.group(1),
                price_tnd=_price(price.group(1)) if price else None,
                image_url=image.group(1) if image else "",
                category_texts=[category_hint, url_category],
                colors=[color.group(1)] if color else [],
                sizes=sizes,
                available=bool(sizes) or "best-taille" not in card,
            )
        if len(found) >= max_raw:
            break
    return list(found.values())


ADAPTERS = {
    "shopify": shopify,
    "woocommerce": woocommerce,
    "prestashop": prestashop,
    "jsonld": jsonld,
    "ha": ha,
    "lyoum": lyoum,
}
