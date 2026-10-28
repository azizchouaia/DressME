// DressMe · M1 wardrobe demo. Vanilla JS, talks to the M1 endpoints (mock or real, same contract).

const API = "/m01";
const params = new URLSearchParams(location.search);
const USER = params.get("user") || "usr_demo";
const DUPLICATE = 0.85;      // config.yaml thresholds.duplicate
const CONFIDENCE = 0.85;     // config.yaml thresholds.confidence
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

const FR = {
  category: {
    top: "Haut", bottom: "Bas", dress: "Robe", outerwear: "Veste & manteau",
    traditional: "Traditionnel", shoes: "Chaussures", accessory: "Accessoire",
  },
  shelf: { accessories: "Accessoires", clothes: "Vêtements", shoes: "Chaussures" },
  season: { spring: "Printemps", summer: "Été", autumn: "Automne", winter: "Hiver" },
  sub: {
    "t-shirt": "t-shirt", shirt: "chemise", "linen shirt": "chemise en lin", "polo shirt": "polo",
    blouse: "blouse", sweater: "pull", sweatshirt: "sweat", hoodie: "sweat à capuche", "tank top": "débardeur",
    jeans: "jean", chinos: "chino", trousers: "pantalon", shorts: "short", skirt: "jupe",
    dress: "robe", "summer dress": "robe d’été", "evening dress": "robe de soirée",
    jacket: "veste", "leather jacket": "veste en cuir", "denim jacket": "veste en jean", blazer: "blazer",
    coat: "manteau", sneakers: "baskets", loafers: "mocassins", boots: "bottines", sandals: "sandales",
    heels: "escarpins", "dress shoes": "chaussures de ville", bag: "sac", belt: "ceinture",
    sunglasses: "lunettes de soleil", hat: "chapeau", scarf: "écharpe", watch: "montre", jewelry: "bijou",
    jebba: "jebba", kachabia: "kachabia", sefsari: "sefsari", blouza: "blouza",
  },
  color: {
    black: "noir", charcoal: "anthracite", grey: "gris", "light grey": "gris clair", white: "blanc",
    cream: "crème", beige: "beige", khaki: "kaki", camel: "camel", tan: "fauve", brown: "marron",
    "dark brown": "brun foncé", navy: "marine", blue: "bleu", denim: "bleu denim", "light blue": "bleu ciel",
    teal: "bleu canard", green: "vert", olive: "olive", mint: "menthe", yellow: "jaune", mustard: "moutarde",
    orange: "orange", red: "rouge", burgundy: "bordeaux", pink: "rose", purple: "violet", lavender: "lavande",
    gold: "doré", silver: "argenté",
  },
  pattern: {
    solid: "uni", striped: "rayé", checked: "à carreaux", floral: "fleuri", "polka dot": "à pois",
    graphic: "imprimé graphique", "animal print": "imprimé animal", embroidered: "brodé",
  },
  material: {
    cotton: "coton", linen: "lin", denim: "denim", leather: "cuir", suede: "daim", wool: "laine",
    silk: "soie", knit: "maille", synthetic: "synthétique",
  },
};
Object.assign(FR, {
  sizeSystem: {
    letter: "Lettres (S, M, L…)", eu: "EU", fr: "FR", us: "US", uk: "UK", it: "IT",
    waist: "Jean (W/L)", shoe_eu: "Pointure EU", shoe_us: "Pointure US", one_size: "Taille unique", other: "Autre",
  },
  condition: { new: "Neuf", good: "Bon état", worn: "Usé", needs_repair: "À réparer" },
  docKind: {
    auto: "Détection automatique", receipt: "Ticket de caisse", price_tag: "Étiquette prix",
    care_label: "Étiquette de composition",
  },
});
const SHELF_OF = {
  top: "clothes", bottom: "clothes", dress: "clothes", outerwear: "clothes", traditional: "clothes",
  shoes: "shoes", accessory: "accessories",
};
const UPPER_RAIL = new Set(["top", "outerwear"]);   // the other clothes hang on the lower rail
const PLACEHOLDER = `${API}/ui/assets/placeholder.svg`;
const HANGER = `<svg class="hanger" viewBox="0 0 120 54" aria-hidden="true" focusable="false">
  <path d="M60 25 V18 C60 14 67 13 67 7 C67 3 63.5 1 60 1 C56.5 1 54 3.5 54 6.5" fill="none" stroke="#81776D" stroke-width="2.6" stroke-linecap="round"/>
  <path d="M60 24 L9 44 Q3 47 7 50 H113 Q117 47 111 44 Z" fill="var(--color-camel)" stroke="var(--color-dark-camel)" stroke-width="1.4" stroke-linejoin="round"/>
  <path d="M13 49 H107" stroke="var(--color-bronze)" stroke-width="3" stroke-linecap="round"/>
</svg>`;

const state = {
  items: [],
  cache: new Map(),       // item_id -> WardrobeItem (also items hidden by the filters)
  dupIds: new Set(),
  newIds: new Set(),
  activeBay: "clothes",
  panelId: null,
  returnFocus: null,
};

// ---------- helpers ----------
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ESC[c]);
const tr = (dict, key) => (key == null ? "" : FR[dict][key] ?? key);
const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s);
const pct = (v) => `${Math.round(v * 100)} %`;
const plural = (n, word) => `${n} ${word}${n > 1 ? "s" : ""}`;
const shelfOf = (item) => item.shelf || SHELF_OF[item.category] || "clothes";
const dateFr = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long", year: "numeric" });
const priceFr = new Intl.NumberFormat("fr-TN", { style: "currency", currency: "TND", minimumFractionDigits: 3 });

const displayable = (src) => Boolean(src) && (src.startsWith("/") || src.startsWith("http"));
function imageOf(item) {
  if (displayable(item.image_cutout)) return item.image_cutout;      // transparent cutout
  return displayable(item.image_raw) ? item.image_raw : PLACEHOLDER;
}
// a raw photo (with its background) is shown as a card; cutouts and SVG silhouettes are shown bare
const isPhoto = (item, src) => src !== item.image_cutout && !/\.svg(\?|$)/i.test(src);
const title = (item) => cap(tr("sub", item.subcategory) || tr("category", item.category));
function altText(item) {
  const main = item.colors?.[0];
  return main ? `${title(item)}, ${tr("color", main.name)}` : title(item);
}
function imgTag(item, extra = "") {
  const src = imageOf(item);
  return `<img src="${esc(src)}" alt="${esc(altText(item))}" class="${isPhoto(item, src) ? "is-photo" : ""}" ${extra}
    onerror="this.onerror=null;this.src='${PLACEHOLDER}';this.classList.remove('is-photo')">`;
}

async function api(path, { method = "POST", body } = {}) {
  const res = await fetch(API + path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail;
    throw new Error(typeof d === "string" ? d : Array.isArray(d) ? d.map((x) => x.msg).join(", ") : `HTTP ${res.status}`);
  }
  return data;
}
const fetchItem = (id) => api(`/items/${encodeURIComponent(id)}?user_id=${encodeURIComponent(USER)}`, { method: "GET" });

function toast(message, kind = "info", { sticky = false, spinner = false } = {}) {
  const el = document.createElement("div");
  el.className = `toast toast--${kind}`;
  el.innerHTML = `${spinner ? '<span class="spinner" aria-hidden="true"></span>' : ""}<span>${esc(message)}</span>`;
  $("#toasts").append(el);
  if (!sticky) setTimeout(() => el.remove(), kind === "error" ? 7000 : 4500);
  return el;
}

// ---------- data ----------
function filters() {
  const body = { user_id: USER };
  const category = $("#f-category").value;
  const season = $("#f-season").value;
  if (category) body.category = category;
  if (season) body.season = season;
  return body;
}

async function loadItems() {
  const data = await api("/items", { body: filters() });
  state.items = data.items;
  data.items.forEach((item) => state.cache.set(item.item_id, item));
  setMode(data.mocked);
  render();
  return data;
}

async function loadDuplicates() {
  try {
    const { groups } = await api("/duplicates", { body: { user_id: USER } });
    state.dupIds = new Set(groups.flat());
  } catch {
    state.dupIds = new Set();
  }
}

function setMode(mocked) {
  const el = $("#mode");
  el.hidden = false;
  el.textContent = mocked ? "Démo · données mock" : "Live · FashionCLIP";
  el.classList.toggle("mode--live", !mocked);
}

// ---------- rendering ----------
function badgeFor(item) {
  if (state.newIds.has(item.item_id)) return '<span class="badge badge--new">Nouveau</span>';
  if (state.dupIds.has(item.item_id)) return '<span class="badge badge--dup">Doublon ?</span>';
  return "";
}

function hangingPiece(item, i) {
  return `<li class="slot" style="--i:${i}">
    <button type="button" class="piece piece--hanging" data-id="${esc(item.item_id)}">
      ${HANGER}${imgTag(item, 'loading="lazy" decoding="async"')}${badgeFor(item)}
    </button></li>`;
}

function flatPiece(item, i) {
  return `<div class="slot" style="--i:${i}">
    <button type="button" class="piece piece--flat" data-id="${esc(item.item_id)}">
      ${imgTag(item, 'loading="lazy" decoding="async"')}${badgeFor(item)}
    </button></div>`;
}

function renderShelves(container, items, perShelf, minShelves, offset) {
  const count = Math.max(minShelves, Math.ceil(items.length / perShelf));
  let html = "";
  for (let s = 0; s < count; s++) {
    const row = items.slice(s * perShelf, (s + 1) * perShelf);
    html += `<div class="shelf">${row.map((it, j) => flatPiece(it, offset + s * perShelf + j)).join("")}</div>`;
  }
  container.innerHTML = items.length ? html : `<p class="bay__empty">Aucune pièce sur ces étagères</p>`;
}

function render() {
  const groups = { accessories: [], clothes: [], shoes: [] };
  state.items.forEach((item) => groups[shelfOf(item)].push(item));

  renderShelves($('[data-shelf="accessories"]'), groups.accessories, 2, 3, 0);
  const upper = groups.clothes.filter((it) => UPPER_RAIL.has(it.category));
  const lower = groups.clothes.filter((it) => !UPPER_RAIL.has(it.category));
  let i = groups.accessories.length;
  $('[data-rail="upper"]').innerHTML = upper.map((it) => hangingPiece(it, i++)).join("")
    || (lower.length ? "" : `<li class="bay__empty">Aucun vêtement sur les tringles</li>`);
  $('[data-rail="lower"]').innerHTML = lower.map((it) => hangingPiece(it, i++)).join("");
  renderShelves($('[data-shelf="shoes"]'), groups.shoes, 2, 3, groups.accessories.length + groups.clothes.length);

  for (const [shelf, list] of Object.entries(groups)) {
    $$(`[data-count="${shelf}"]`).forEach((el) => {
      el.textContent = el.closest(".bay-nav") ? `(${list.length})` : plural(list.length, "pièce");
    });
  }
  const filtered = $("#f-category").value || $("#f-season").value;
  $("#total").textContent = `${plural(state.items.length, "pièce")}${filtered ? " (filtrées)" : ""}`;
  setActiveBay(state.activeBay);
}

function setActiveBay(bay) {
  state.activeBay = bay;
  $$(".bay-nav button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.bay === bay)));
  $$(".bay").forEach((s) => s.classList.toggle("is-active", s.dataset.bay === bay));
}

// ---------- doors ----------
const wardrobe = $("#wardrobe");
const interior = $("#interior");

function afterDoors(callback) {
  const door = $(".door--left");
  let done = false;
  const finish = () => {
    if (done) return;
    done = true;
    door.removeEventListener("transitionend", finish);
    callback();
  };
  door.addEventListener("transitionend", finish);
  setTimeout(finish, reduceMotion.matches ? 30 : 900);
}

function openWardrobe() {
  if (wardrobe.dataset.state !== "closed") return;
  wardrobe.dataset.state = "opening";
  wardrobe.classList.add("is-revealing");
  $("#toolbar").hidden = false;
  interior.inert = false;
  afterDoors(() => {
    wardrobe.dataset.state = "open";
    const first = $(".bay.is-active .piece") || $(".piece");
    (first || $("#add")).focus({ preventScroll: true });
    if (!state.resumed) {
      state.resumed = true;
      resumePending();
    }
  });
  setTimeout(() => wardrobe.classList.remove("is-revealing"), reduceMotion.matches ? 50 : 1700);
}

function closeWardrobe() {
  if (wardrobe.dataset.state !== "open") return;
  closePanel(false);
  wardrobe.dataset.state = "closing";
  interior.inert = true;
  $("#toolbar").hidden = true;
  afterDoors(() => {
    wardrobe.dataset.state = "closed";
    $("#open").focus();
  });
}

// ---------- side panel ----------
const panel = $("#panel");

function meter(label, value, { ends, ok } = {}) {
  return `<div class="meter-row">
    <div class="meter-row__top"><span>${label}</span><strong>${pct(value)}</strong></div>
    <div class="meter ${ok ? "meter--ok" : ""}" role="meter" aria-label="${esc(label)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(value * 100)}"><span style="--v:${value}"></span></div>
    ${ends ? `<div class="meter-row__ends"><span>${ends[0]}</span><span>${ends[1]}</span></div>` : ""}
  </div>`;
}

const formatComposition = (list) => (list || []).map((m) => `${+m.percent} % ${m.material}`).join(", ");

function infoHTML(item) {
  const bought = item.purchase_date ? dateFr.format(new Date(item.purchase_date)) : item.purchase_year;
  const rows = [
    item.price_tnd != null ? ["Prix", esc(priceFr.format(item.price_tnd))] : null,
    item.size ? ["Taille", `${esc(item.size)}${item.size_system ? ` <small>(${esc(tr("sizeSystem", item.size_system))})</small>` : ""}`] : null,
    item.brand ? ["Marque", esc(item.brand)] : null,
    bought || item.store ? ["Achat", [bought, item.store].filter(Boolean).map(esc).join(" · ")] : null,
    item.reference ? ["Référence", esc(item.reference)] : null,
    item.composition?.length ? ["Composition", esc(formatComposition(item.composition))] : null,
    item.care?.length ? ["Entretien", item.care.map(esc).join("<br>")] : null,
    item.condition ? ["État", esc(tr("condition", item.condition))] : null,
    item.notes ? ["Notes", esc(item.notes)] : null,
    item.receipt_image ? ["Ticket", `<a href="${esc(item.receipt_image)}" target="_blank" rel="noopener">Voir le ticket conservé</a>`] : null,
  ].filter(Boolean);
  return `<section class="sheet__section">
      <div class="sheet__section-head"><h3>Informations</h3>
        <button type="button" class="btn btn--link" data-edit="${esc(item.item_id)}">${rows.length ? "Modifier" : "Ajouter"}</button></div>
      ${rows.length ? `<dl class="facts">${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>`
        : '<p class="muted">Taille, prix, marque, achat… : ajoutez-les à la main ou scannez le ticket.</p>'}
    </section>`;
}

function sheetHTML(item) {
  const isDup = state.dupIds.has(item.item_id);
  const colors = (item.colors || []).map((c) => `<li class="swatch"><i style="--c:${esc(c.hex)}" aria-hidden="true"></i>
      ${esc(cap(tr("color", c.name)))} <small>${pct(c.share)}</small></li>`).join("");
  const seasons = (item.season || []).map((s) => `<span class="chip">${esc(tr("season", s))}</span>`).join("");
  const badges = [
    state.newIds.has(item.item_id) ? '<span class="badge badge--new">Nouveau</span>' : "",
    `<span class="badge badge--dup" id="dup-badge" ${state.dupIds.has(item.item_id) ? "" : "hidden"}>Doublon possible</span>`,
    item.confidence != null && item.confidence < CONFIDENCE ? '<span class="badge badge--warn">À confirmer</span>' : "",
    item.local_tag ? '<span class="badge badge--local">Pièce tunisienne</span>' : "",
  ].join("");
  const facts = [
    ["Saison", seasons ? `<div class="chips">${seasons}</div>` : "—"],
    ["Motif", esc(cap(tr("pattern", item.pattern)) || "—")],
    ["Matière", esc(cap(tr("material", item.material)) || "—")],
    ["Portée", `${plural(item.wear_count || 0, "fois")}${item.last_worn ? ` · dernière le ${esc(dateFr.format(new Date(item.last_worn)))}` : ""}`],
  ].filter(Boolean).map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("");

  return `
    <figure class="sheet__media">${imgTag(item)}</figure>
    <p class="sheet__eyebrow">${esc(tr("category", item.category))} · Rayon ${esc(tr("shelf", shelfOf(item)).toLowerCase())}</p>
    <h2 class="sheet__title" id="panel-title">${esc(title(item))}</h2>
    <div class="sheet__badges">${badges}</div>
    <section class="sheet__section"><h3>Couleurs</h3>
      ${colors ? `<ul class="swatches">${colors}</ul>` : '<p class="muted">Aucune couleur détectée</p>'}</section>
    ${infoHTML(item)}
    <section class="sheet__section"><h3>Détails</h3><dl class="facts">${facts}</dl></section>
    <section class="sheet__section"><h3>Analyse</h3>
      ${item.formality != null ? meter("Formalité", item.formality, { ends: ["Décontracté", "Habillé"] }) : ""}
      ${item.confidence != null ? meter("Confiance du classifieur", item.confidence, { ok: item.confidence >= CONFIDENCE }) : ""}
    </section>
    <section class="sheet__section"><h3>Pièces similaires</h3>
      <div class="similar" id="similar-list" aria-live="polite" aria-busy="true"><div class="skeleton"></div><div class="skeleton"></div></div>
    </section>
    <div class="sheet__actions">
      <button type="button" class="btn btn--primary" id="donate-btn" data-donate="${esc(item.item_id)}" ${isDup ? "" : "hidden"}>Donner cette pièce</button>
      <button type="button" class="btn btn--ghost btn--danger" data-delete="${esc(item.item_id)}">Retirer de la garde-robe</button>
      <p class="sheet__hint" id="donate-hint" ${isDup ? "" : "hidden"}>Vous avez une pièce très proche : celle-ci peut faire plaisir à quelqu’un d’autre.</p>
    </div>`;
}

async function openPanel(id, trigger, { edit = false, intro = false } = {}) {
  let item = state.cache.get(id);
  if (!item) {
    try {
      item = await fetchItem(id);
      state.cache.set(id, item);
    } catch (e) {
      toast(`Pièce introuvable : ${e.message}`, "error");
      return;
    }
  }
  if (panel.hidden) state.returnFocus = trigger || document.activeElement;
  state.panelId = id;
  $("#panel-body").innerHTML = edit ? formHTML(item, intro) : sheetHTML(item);
  panel.hidden = false;
  $("#scrim").hidden = false;
  document.body.classList.add("no-scroll");
  panel.scrollTop = 0;
  if (edit) {
    initForm(item, intro);
    $("#doc-scan").focus();
  } else {
    $("#panel-close").focus();
    loadSimilar(item);
  }
}

async function loadSimilar(item) {
  const box = $("#similar-list");
  try {
    const { neighbours } = await api("/similar", { body: { user_id: USER, item_id: item.item_id, k: 6 } });
    const resolved = await Promise.all(neighbours.map(async (n) => {
      let other = state.cache.get(n.item_id);
      if (!other) {
        other = await fetchItem(n.item_id).catch(() => null);
        if (other) state.cache.set(n.item_id, other);
      }
      return { n, other };
    }));
    if (state.panelId !== item.item_id) return;          // the user opened another item meanwhile
    if (neighbours.some((n) => n.similarity >= DUPLICATE)) {
      ["#dup-badge", "#donate-btn", "#donate-hint"].forEach((sel) => { $(sel).hidden = false; });
    }
    const cards = resolved.filter((r) => r.other).map(({ n, other }) => `
      <button type="button" class="similar__item" data-similar="${esc(other.item_id)}">
        ${imgTag(other, 'loading="lazy"')}
        <span class="similar__name">${esc(title(other))}</span>
        <span class="similar__score">${pct(n.similarity)} similaire</span>
        ${n.similarity >= DUPLICATE ? '<span class="badge badge--dup">Doublon possible</span>' : ""}
      </button>`).join("");
    box.innerHTML = cards || '<p class="muted">Aucune pièce similaire au-dessus du seuil (75 %).</p>';
  } catch (e) {
    if (state.panelId === item.item_id) box.innerHTML = `<p class="muted">Impossible de charger les pièces similaires (${esc(e.message)}).</p>`;
  } finally {
    box.removeAttribute("aria-busy");
  }
}

function closePanel(restoreFocus = true) {
  if (panel.hidden) return;
  panel.hidden = true;
  $("#scrim").hidden = true;
  document.body.classList.remove("no-scroll");
  state.panelId = null;
  if (restoreFocus && state.returnFocus?.isConnected) state.returnFocus.focus();
  state.returnFocus = null;
}

function trapFocus(e) {
  if (e.key === "Escape") {
    e.preventDefault();
    closePanel();
    return;
  }
  if (e.key !== "Tab") return;
  const focusables = $$('button:not([disabled]), [href], select, input, [tabindex]:not([tabindex="-1"])', panel)
    .filter((el) => el.offsetParent !== null);
  if (!focusables.length) return;
  const first = focusables[0];
  const last = focusables[focusables.length - 1];
  if (e.shiftKey && document.activeElement === first) {
    e.preventDefault();
    last.focus();
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault();
    first.focus();
  }
}

async function deleteItem(id) {
  const item = state.cache.get(id);
  if (!window.confirm(`Retirer « ${item ? title(item) : id} » de la garde-robe ?`)) return;
  try {
    await api(`/items/${encodeURIComponent(id)}?user_id=${encodeURIComponent(USER)}`, { method: "DELETE" });
    state.cache.delete(id);
    state.dupIds.delete(id);
    closePanel(false);
    await loadDuplicates();
    await loadItems();
    toast(`${item ? title(item) : "Pièce"} retirée de la garde-robe.`, "success");
    ($(".piece") || $("#add")).focus();
  } catch (e) {
    toast(`Suppression impossible : ${e.message}`, "error");
  }
}

// ---------- donation of a duplicate: confirmation screen + "À donner" bag ----------
const PLACES = { association: "Une association locale", friend: "Un proche", other: "Autre" };

// ---------- "Où la donner ?": places of the verified list, picked and explained by the local LLM ----------
const CITIES = ["Tunis", "Ariana", "Ben Arous", "Manouba", "Nabeul", "Bizerte", "Béja", "Jendouba", "Sousse",
  "Monastir", "Mahdia", "Sfax", "Kairouan", "Kasserine", "Gafsa", "Gabès", "Médenine", "Autre"];   // donation_places.json
const CITY_KEY = "dressme.m01.city";
let giveToken = 0;

function savedCity() {
  try { return localStorage.getItem(CITY_KEY) || "Tunis"; } catch { return "Tunis"; }
}

async function loadDonationIdeas(item) {
  const token = ++giveToken;
  const city = $("#donate-city").value;
  try { localStorage.setItem(CITY_KEY, city); } catch { /* private mode */ }
  $("#donate-message").textContent = "Le coach cherche où cette pièce peut faire plaisir…";
  $("#donate-list").innerHTML = "";
  $("#donate-meta").textContent = "";
  let r;
  try {
    r = await api(`/items/${encodeURIComponent(item.item_id)}/donation-suggestions?user_id=${encodeURIComponent(USER)}`,
      { body: { city: city === "Autre" ? null : city } });
  } catch (e) {
    if (token === giveToken) $("#donate-message").textContent = `Suggestions indisponibles : ${e.message}`;
    return;
  }
  if (token !== giveToken) return;   // the city changed meanwhile
  $("#donate-message").textContent = r.message;
  $("#donate-list").innerHTML = r.suggestions.map((s) => `<li><button type="button" class="give__item" data-place="${esc(s.place)}" aria-pressed="false">
      <span class="give__name">${esc(s.name)}</span>
      <span class="give__reason">${esc(s.reason)}</span>
      <span class="give__how">${esc(s.how)}</span>
      ${s.url || s.phone ? `<span class="give__links">${s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">Site officiel ↗</a>` : ""}${
        s.phone ? `<a href="tel:${esc(s.phone.replace(/\s/g, ""))}">${esc(s.phone)}</a>` : ""}${s.address ? `<span>${esc(s.address)}</span>` : ""}</span>` : ""}
    </button></li>`).join("");
  $("#donate-meta").textContent = r.llm_used
    ? `Choisi et expliqué par ${r.model} (local) parmi une liste vérifiée · ${(r.elapsed_ms / 1000).toFixed(1)} s`
    : "Liste vérifiée (LLM local indisponible : ordre par défaut)";
}

/** Confirmation screen; resolves to {place} (null = not decided yet) or null when cancelled. */
function askDonation(item) {
  const layer = $("#donate-layer");
  $("#donate-title").textContent = `Donner « ${title(item)} » ?`;
  $("#donate-piece").innerHTML = dupCard(item, "À donner", null, true);
  $$('input[name="place"]', layer).forEach((r) => { r.checked = r.value === ""; });
  const city = $("#donate-city");
  if (!city.options.length) city.innerHTML = CITIES.map((c) => `<option>${esc(c)}</option>`).join("");
  city.value = CITIES.includes(savedCity()) ? savedCity() : "Tunis";
  city.onchange = () => loadDonationIdeas(item);
  loadDonationIdeas(item);
  const previous = document.activeElement;
  layer.hidden = false;
  $("#donate-ok").focus();
  return new Promise((resolve) => {
    const done = (value) => {
      layer.hidden = true;
      layer.removeEventListener("click", onClick);
      layer.removeEventListener("keydown", onKey);
      if (previous?.isConnected) previous.focus({ preventScroll: true });
      giveToken += 1;   // a late LLM answer must not fill the closed dialog
      resolve(value);
    };
    const onClick = (e) => {
      const idea = e.target.closest(".give__item");
      if (idea && !e.target.closest("a")) {   // picking a suggestion fills "À qui ?"
        $$(".give__item", layer).forEach((b) => b.setAttribute("aria-pressed", String(b === idea)));
        $$('input[name="place"]', layer).forEach((r) => { r.checked = r.value === idea.dataset.place; });
        return;
      }
      if (e.target.closest("#donate-ok")) done({ place: $('input[name="place"]:checked', layer)?.value || null });
      else if (e.target.closest("#donate-cancel") || e.target === layer) done(null);
    };
    const onKey = (e) => {
      if (e.key === "Escape") { e.preventDefault(); done(null); }
    };
    layer.addEventListener("click", onClick);
    layer.addEventListener("keydown", onKey);
  });
}

async function donateItem(id) {
  const item = state.cache.get(id) || await fetchItem(id).catch(() => null);
  if (!item) return;
  const choice = await askDonation(item);
  if (!choice) return;
  try {
    await api(`/items/${encodeURIComponent(id)}/donate?user_id=${encodeURIComponent(USER)}`, { body: choice });
    state.cache.delete(id);
    closePanel(false);
    await loadDuplicates();
    await loadItems();
    await refreshBagCount();
    toast(`« ${title(item)} » est dans votre sac À donner.`, "success");
  } catch (e) {
    toast(`Don impossible : ${e.message}`, "error");
  }
}

async function donatedItems() {
  return (await api("/items", { body: { user_id: USER, status: "donated" } })).items;
}

async function refreshBagCount() {
  try {
    const n = (await donatedItems()).length;
    $("#bag-count").textContent = n ? String(n) : "";
  } catch { /* the bag count is optional */ }
}

async function openBag() {
  let items;
  try { items = await donatedItems(); } catch (e) { toast(e.message, "error"); return; }
  items.sort((a, b) => String(b.donated_at).localeCompare(String(a.donated_at)));
  const rows = items.map((it) => `<li class="bag__item">${imgTag(it, 'loading="lazy"')}
      <div><div class="bag__name">${esc(title(it))}</div>
      <div class="bag__meta">${it.donated_at ? `Mise de côté le ${esc(dateFr.format(new Date(it.donated_at)))}` : ""}${
        it.donation_place ? ` · ${esc(PLACES[it.donation_place] || it.donation_place)}` : ""}</div></div></li>`).join("");
  if (panel.hidden) state.returnFocus = $("#bag");
  state.panelId = null;
  $("#panel-body").innerHTML = `<p class="sheet__eyebrow">Sac</p>
    <h2 class="sheet__title" id="panel-title">À donner</h2>
    <p class="muted">${items.length ? `${plural(items.length, "pièce")} prête${items.length > 1 ? "s" : ""} à faire une seconde vie.`
      : "Votre sac est vide. Ouvrez une pièce en double pour la donner."}</p>
    ${rows ? `<ul class="bag">${rows}</ul>` : ""}`;
  panel.hidden = false;
  $("#scrim").hidden = false;
  document.body.classList.add("no-scroll");
  panel.scrollTop = 0;
  $("#panel-close").focus();
}

// ---------- details form (size, price, brand…) + receipt / label scan ----------
const attrs = (a) => Object.entries(a).map(([k, v]) => `${k}="${esc(v)}"`).join(" ");
const fieldLabel = (label) => `<span class="field__label">${label} <span class="detected-tag" hidden>détecté</span></span>`;
function inputField(name, label, value, a = {}) {
  return `<label class="field" data-field="${name}">${fieldLabel(label)}<input name="${name}" value="${esc(value ?? "")}" ${attrs(a)}></label>`;
}
function selectField(name, label, dict, value, empty = "—") {
  const options = Object.entries(FR[dict])
    .map(([k, l]) => `<option value="${k}" ${k === value ? "selected" : ""}>${esc(l)}</option>`).join("");
  return `<label class="field" data-field="${name}">${fieldLabel(label)}<select name="${name}">${empty == null ? "" : `<option value="">${empty}</option>`}${options}</select></label>`;
}
function textareaField(name, label, value, a = {}) {
  return `<label class="field field--wide" data-field="${name}">${fieldLabel(label)}<textarea name="${name}" ${attrs(a)}>${esc(value ?? "")}</textarea></label>`;
}

function formHTML(item, intro) {
  const seasons = Object.entries(FR.season).map(([k, l]) =>
    `<label class="check"><input type="checkbox" name="season" value="${k}" ${item.season?.includes(k) ? "checked" : ""}> ${l}</label>`).join("");
  const kinds = Object.entries(FR.docKind).map(([k, l]) => `<option value="${k}">${esc(l)}</option>`).join("");
  return `
  <form class="form" id="details-form" novalidate>
    <p class="sheet__eyebrow">${intro ? "Nouvelle pièce" : "Modifier"} · ${esc(title(item))}</p>
    <h2 class="sheet__title" id="panel-title">${intro ? "Complétez les informations" : "Informations de la pièce"}</h2>
    <p class="muted">${intro ? "Facultatif : vous pourrez le faire plus tard depuis la fiche de la pièce."
      : "Seuls les champs modifiés sont enregistrés. Videz un champ pour l’effacer."}</p>
    <div class="form__error" id="form-error" role="alert" hidden></div>

    <section class="scan" aria-labelledby="scan-title">
      <h3 id="scan-title">Scanner un ticket ou une étiquette</h3>
      <p class="muted">Les informations lues pré-remplissent le formulaire : vérifiez-les avant d’enregistrer.</p>
      <div class="scan__row">
        <label class="field"><span class="field__label">Document</span><select id="doc-kind">${kinds}</select></label>
        <button type="button" class="btn btn--ghost" id="doc-scan">
          <svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true" focusable="false"><path d="M3 6.5h3l1.5-2h5L14 6.5h3v9H3z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><circle cx="10" cy="11" r="2.8" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>
          Choisir une photo</button>
        <input type="file" id="doc-file" accept="image/*" hidden>
      </div>
      <label class="check"><input type="checkbox" id="doc-keep" disabled> Garder l’image du ticket avec la pièce</label>
      ${item.receipt_image ? `<label class="check"><input type="checkbox" id="doc-remove"> Supprimer le ticket conservé
        (<a href="${esc(item.receipt_image)}" target="_blank" rel="noopener">voir</a>)</label>` : ""}
      <div class="scan__status" id="doc-status" aria-live="polite"></div>
      <div id="doc-lines"></div>
    </section>

    <fieldset class="form__section"><legend>Achat</legend><div class="form__grid">
      ${inputField("price_tnd", "Prix (TND)", item.price_tnd?.toFixed(3), { type: "number", step: "0.001", min: "0", inputmode: "decimal", placeholder: "89.000" })}
      ${inputField("store", "Magasin", item.store, { placeholder: "Zara · Tunisia Mall", maxlength: 120 })}
      ${inputField("purchase_date", "Date d’achat", item.purchase_date, { type: "date" })}
      ${inputField("purchase_year", "… ou seulement l’année", item.purchase_year, { type: "number", min: 1950, max: 2100, placeholder: "2015" })}
    </div></fieldset>

    <fieldset class="form__section"><legend>Identité</legend><div class="form__grid">
      ${inputField("brand", "Marque", item.brand, { maxlength: 80 })}
      ${inputField("reference", "Référence", item.reference, { maxlength: 60 })}
      ${inputField("size", "Taille", item.size, { maxlength: 20, placeholder: "M, 40, W32 L34" })}
      ${selectField("size_system", "Système de taille", "sizeSystem", item.size_system)}
    </div></fieldset>

    <fieldset class="form__section"><legend>Matière et entretien</legend><div class="form__grid">
      ${inputField("composition", "Composition", formatComposition(item.composition), { placeholder: "55 % lin, 45 % coton" })}
      ${selectField("condition", "État", "condition", item.condition)}
      ${textareaField("care", "Entretien (une consigne par ligne)", (item.care || []).join("\n"), { rows: 3 })}
      ${textareaField("notes", "Notes", item.notes, { rows: 2, maxlength: 1000 })}
    </div></fieldset>

    <fieldset class="form__section"><legend>Corriger l’analyse</legend><div class="form__grid">
      ${selectField("category", "Catégorie", "category", item.category, null)}
      ${inputField("subcategory", "Type", item.subcategory, { maxlength: 64 })}
      ${inputField("pattern", "Motif", item.pattern, { maxlength: 32 })}
      ${inputField("material", "Matière principale", item.material, { maxlength: 32 })}
      <div class="field field--wide"><span class="field__label">Saisons</span><div class="checks">${seasons}</div></div>
    </div></fieldset>

    <div class="form__actions">
      <button type="button" class="btn btn--ghost" id="form-cancel">${intro ? "Plus tard" : "Annuler"}</button>
      <button type="submit" class="btn btn--primary" id="form-save">Enregistrer</button>
    </div>
  </form>`;
}

function parseComposition(text) {
  const out = [];
  for (const m of text.matchAll(/(\d+(?:[.,]\d+)?)\s*%\s*([^,;/\n\d]+)/g)) {
    out.push({ material: m[2].trim().toLowerCase(), percent: parseFloat(m[1].replace(",", ".")) });
  }
  if (!out.length) {                                   // "lin 100 %"
    for (const m of text.matchAll(/([^,;/\n\d%]+?)\s*(\d+(?:[.,]\d+)?)\s*%/g)) {
      out.push({ material: m[1].trim().toLowerCase(), percent: parseFloat(m[2].replace(",", ".")) });
    }
  }
  return out;
}

/** Form values in the shape of the API (ItemUpdate), and only those that changed. */
function readForm(form, item) {
  const fd = new FormData(form);
  const str = (n) => { const v = String(fd.get(n) ?? "").trim(); return v === "" ? null : v; };
  const num = (n) => { const v = str(n); return v == null ? null : Number(v.replace(",", ".")); };
  const compositionText = str("composition") ?? "";
  const composition = parseComposition(compositionText);
  if (compositionText && !composition.length) throw new Error("Composition : écrivez par exemple « 55 % lin, 45 % coton ».");
  const values = {
    price_tnd: num("price_tnd"), store: str("store"), purchase_date: str("purchase_date"), purchase_year: num("purchase_year"),
    brand: str("brand"), reference: str("reference"), size: str("size"), size_system: str("size_system"),
    composition, condition: str("condition"), notes: str("notes"),
    care: (str("care") ?? "").split("\n").map((s) => s.trim()).filter(Boolean),
    category: str("category"), subcategory: str("subcategory"), pattern: str("pattern"), material: str("material"),
    season: fd.getAll("season"),
  };
  const lists = new Set(["composition", "care", "season"]);
  const before = (k) => {
    const v = item[k];
    if (k === "composition") return (v || []).map((m) => ({ material: m.material, percent: +m.percent }));
    if (lists.has(k)) return v || [];
    return v ?? null;
  };
  const changes = {};
  for (const [k, v] of Object.entries(values)) {
    if (JSON.stringify(v) !== JSON.stringify(before(k))) changes[k] = v;
  }
  return changes;
}

function markDetected(form, name) {
  const wrap = form.querySelector(`[data-field="${name}"]`);
  if (!wrap) return;
  wrap.classList.add("is-detected");
  wrap.querySelector(".detected-tag").hidden = false;
}

function applyExtraction(form, doc) {
  const f = doc.fields;
  let filled = 0;
  const set = (name, value) => {
    if (value == null || value === "" || (Array.isArray(value) && !value.length)) return;
    form.elements[name].value = value;
    markDetected(form, name);
    filled += 1;
  };
  const notes = [];
  if (f.price != null) {
    if (!f.currency || f.currency === "TND") set("price_tnd", f.price.toFixed(3));
    else notes.push(`prix lu : ${f.price} ${esc(f.currency)} (non converti en TND)`);
  }
  set("purchase_date", f.purchase_date);
  if (f.purchase_date) set("purchase_year", f.purchase_date.slice(0, 4));
  set("store", f.store);
  set("brand", f.brand);
  set("reference", f.reference);
  set("size", f.size);
  set("size_system", f.size_system);
  set("composition", formatComposition(f.composition));
  set("care", (f.care || []).join("\n"));

  const linesBox = $("#doc-lines");
  if (doc.lines.length > 1) {
    linesBox.innerHTML = `<fieldset class="scan__lines"><legend>Quelle ligne du ticket correspond à cette pièce ?</legend>
      ${doc.lines.map((l, i) => `<label class="check"><input type="radio" name="receipt-line" value="${i}" ${i === doc.selected_line ? "checked" : ""}>
        <span>${esc(l.label)}</span>${l.price != null ? `<strong>${esc(priceFr.format(l.price))}</strong>` : ""}</label>`).join("")}
    </fieldset>`;
    linesBox.querySelectorAll('input[name="receipt-line"]').forEach((radio) => radio.addEventListener("change", () => {
      const line = doc.lines[+radio.value];
      if (line.price != null && (!f.currency || f.currency === "TND")) {
        form.elements.price_tnd.value = line.price.toFixed(3);
        markDetected(form, "price_tnd");
      }
    }));
  } else {
    linesBox.innerHTML = "";
  }
  const what = tr("docKind", doc.kind).toLowerCase();
  $("#doc-status").innerHTML = `<span class="badge badge--new">Lu</span> ${esc(cap(what))} : ${plural(filled, "champ")} pré-rempli${filled > 1 ? "s" : ""}.`
    + (doc.lines.length > 1 && doc.selected_line == null ? " Choisissez la ligne de cette pièce ci-dessous." : "")
    + (notes.length ? ` <span class="muted">(${notes.join(" ; ")})</span>` : "")
    + (doc.mocked ? ' <span class="muted">(démo)</span>' : "");
}

function initForm(item, intro) {
  const form = $("#details-form");
  let docImage = null;
  form.addEventListener("input", (e) => {
    const wrap = e.target.closest(".is-detected");
    if (wrap) {
      wrap.classList.remove("is-detected");
      wrap.querySelector(".detected-tag").hidden = true;
    }
  });
  $("#doc-scan").addEventListener("click", () => $("#doc-file").click());
  $("#doc-file").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    const status = $("#doc-status");
    status.innerHTML = '<span class="spinner spinner--dark" aria-hidden="true"></span> Lecture du document…';
    $("#doc-scan").disabled = true;
    try {
      docImage = await toDataURL(file);
      $("#doc-keep").disabled = false;
      const body = { user_id: USER, image: docImage, kind: $("#doc-kind").value, item_id: item.item_id };
      applyExtraction(form, await api("/documents/extract", { body }));
    } catch (err) {
      status.innerHTML = /503|indisponible|unavailable/i.test(err.message)
        ? "La lecture automatique n’est pas encore disponible (module M8). Complétez le formulaire à la main : vous pouvez quand même garder l’image du ticket."
        : `Lecture impossible : ${esc(err.message)}`;
    } finally {
      $("#doc-scan").disabled = false;
    }
  });
  $("#form-cancel").addEventListener("click", () => (intro ? closePanel() : openPanel(item.item_id)));
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const error = $("#form-error");
    error.hidden = true;
    let changes;
    try {
      changes = readForm(form, item);
    } catch (err) {
      error.textContent = err.message;
      error.hidden = false;
      return;
    }
    if ($("#doc-keep").checked && docImage) changes.receipt_image = docImage;
    if ($("#doc-remove")?.checked) changes.receipt_image = null;
    if (!Object.keys(changes).length) {
      openPanel(item.item_id);
      return;
    }
    $("#form-save").disabled = true;
    try {
      const url = `/items/${encodeURIComponent(item.item_id)}?user_id=${encodeURIComponent(USER)}`;
      const saved = await api(url, { method: "PATCH", body: changes });
      state.cache.set(saved.item_id, saved);
      await loadItems();
      await openPanel(saved.item_id);
      toast("Informations enregistrées.", "success");
    } catch (err) {
      error.textContent = `Enregistrement impossible : ${err.message}`;
      error.hidden = false;
      $("#form-save").disabled = false;
    }
  });
}

// ---------- add a photo ----------
function readAsDataURL(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

async function toDataURL(file, maxSide = 1280) {
  const bitmap = await createImageBitmap(file).catch(() => null);
  if (!bitmap) return readAsDataURL(file);
  const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
  if (scale === 1 && file.size < 3_000_000) return readAsDataURL(file);
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL(file.type === "image/png" ? "image/png" : "image/jpeg", 0.9);
}

async function addPhoto(file) {
  if (!file.type.startsWith("image/")) {
    toast("Ce fichier n’est pas une image.", "error");
    return;
  }
  const addBtn = $("#add");
  addBtn.disabled = true;
  addBtn.setAttribute("aria-busy", "true");
  const pending = toast("Analyse de la photo : détourage, classification, couleurs…", "info", { sticky: true, spinner: true });
  try {
    const image = await toDataURL(file);
    const res = await api("/classify", { body: { user_id: USER, image, mode: "add_to_wardrobe" } });
    let g = res.garment;
    if (res.pending) {
      // M1 held the piece (status "pending"): nothing is added until the user decides
      pending.remove();
      g = await resolvePending(g, res.duplicates);
      if (!g) return;
    }
    state.cache.set(g.item_id, g);
    state.newIds.add(g.item_id);
    if (res.duplicates.length) {
      state.dupIds.add(g.item_id);
      res.duplicates.forEach((d) => state.dupIds.add(d.item_id));
    }
    const category = $("#f-category").value;
    const season = $("#f-season").value;
    if ((category && category !== g.category) || (season && !g.season.includes(season))) $("#filters").reset();
    state.activeBay = shelfOf(g);
    await loadItems();

    const piece = interior.querySelector(`[data-id="${CSS.escape(g.item_id)}"]`);
    if (piece) {
      piece.closest(".slot").classList.add("slot--enter");
      piece.scrollIntoView({ behavior: reduceMotion.matches ? "auto" : "smooth", block: "nearest", inline: "center" });
      piece.focus({ preventScroll: true });
    }
    toast(`Nouvelle pièce « ${title(g)} », rangée dans le rayon ${tr("shelf", shelfOf(g)).toLowerCase()}.`, "success");
    if (res.needs_confirmation) toast(`Confiance ${pct(g.confidence)} : vérifiez la catégorie proposée.`, "warn");
    openPanel(g.item_id, piece, { edit: true, intro: true });          // optional: size, price, receipt…
  } catch (e) {
    toast(`Échec de l’analyse : ${e.message}`, "error");
  } finally {
    pending.remove();
    addBtn.disabled = false;
    addBtn.removeAttribute("aria-busy");
  }
}

// ---------- possible duplicate: accept or cancel ----------
function dupCard(item, label, score, isNew = false) {
  return `<figure class="dup-card ${isNew ? "dup-card--new" : ""}">
    <figcaption class="dup-card__label">${label}</figcaption>
    ${imgTag(item)}
    <span class="dup-card__name">${esc(title(item))}</span>
    ${score != null ? `<span class="dup-card__score">${pct(score)} similaire</span>` : ""}
  </figure>`;
}

/** Shows the comparison and resolves to "accept" or "cancel" (Esc and backdrop = cancel, the safe choice). */
async function askDuplicate(item, duplicates) {
  const existing = await Promise.all(duplicates.slice(0, 2).map(async (d) => {
    let other = state.cache.get(d.item_id);
    if (!other) {
      other = await fetchItem(d.item_id).catch(() => null);
      if (other) state.cache.set(d.item_id, other);
    }
    return other ? dupCard(other, "Déjà dans votre garde-robe", d.similarity) : "";
  }));
  $("#dup-compare").innerHTML = dupCard(item, "Nouvelle photo", null, true) + existing.join("");
  const layer = $("#dup-layer");
  const previous = document.activeElement;
  layer.hidden = false;
  document.body.classList.add("no-scroll");
  $("#dup-cancel").focus();

  return new Promise((resolve) => {
    const done = (decision) => {
      layer.hidden = true;
      document.body.classList.remove("no-scroll");
      layer.removeEventListener("keydown", onKey);
      layer.removeEventListener("click", onClick);
      if (previous?.isConnected) previous.focus({ preventScroll: true });
      resolve(decision);
    };
    const onClick = (e) => {
      if (e.target.closest("#dup-accept")) done("accept");
      else if (e.target.closest("#dup-cancel") || e.target === layer) done("cancel");
    };
    const onKey = (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        done("cancel");
      } else if (e.key === "Tab") {             // focus stays on the two buttons
        e.preventDefault();
        (document.activeElement === $("#dup-cancel") ? $("#dup-accept") : $("#dup-cancel")).focus();
      }
    };
    layer.addEventListener("click", onClick);
    layer.addEventListener("keydown", onKey);
  });
}

/** Asks the user, then confirms (returns the active item) or cancels (deletes it, returns null). */
async function resolvePending(item, duplicates) {
  const decision = await askDuplicate(item, duplicates);
  const url = `/items/${encodeURIComponent(item.item_id)}`;
  const user = `user_id=${encodeURIComponent(USER)}`;
  if (decision === "cancel") {
    await api(`${url}?${user}`, { method: "DELETE" });
    toast("Ajout annulé : la pièce n’a pas été ajoutée à la garde-robe.", "info");
    return null;
  }
  const active = await api(`${url}/confirm?${user}`, { method: "POST" });
  state.dupIds.add(active.item_id);
  duplicates.forEach((d) => state.dupIds.add(d.item_id));
  return active;
}

/** Pieces left pending (page closed before deciding) are asked again when the wardrobe opens. */
async function resumePending() {
  let held = [];
  try {
    held = (await api("/items", { body: { user_id: USER, status: "pending" } })).items;
  } catch {
    return;
  }
  for (const item of held) {
    let duplicates = [];
    try {
      const body = { user_id: USER, item_id: item.item_id, k: 2, threshold: DUPLICATE };
      duplicates = (await api("/similar", { body })).neighbours;
    } catch { /* still ask, without the comparison */ }
    try {
      const active = await resolvePending(item, duplicates);
      if (active) {
        state.newIds.add(active.item_id);
        await loadItems();
        toast(`« ${title(active)} » ajoutée à la garde-robe.`, "success");
      }
    } catch (e) {
      toast(`Décision non enregistrée : ${e.message}`, "error");
    }
  }
}

// ---------- wiring ----------
function bind() {
  $("#user").textContent = USER;
  $("#open").addEventListener("click", openWardrobe);
  $("#doors").addEventListener("click", openWardrobe);
  $("#close").addEventListener("click", closeWardrobe);

  interior.addEventListener("click", (e) => {
    const piece = e.target.closest(".piece");
    if (piece) openPanel(piece.dataset.id, piece);
  });
  $(".bay-nav").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-bay]");
    if (btn) setActiveBay(btn.dataset.bay);
  });

  $("#filters").addEventListener("change", () => loadItems().catch((e) => toast(e.message, "error")));
  $("#filters").addEventListener("reset", () => setTimeout(() => loadItems().catch((e) => toast(e.message, "error"))));
  $("#filters").addEventListener("submit", (e) => e.preventDefault());

  $("#add").addEventListener("click", () => $("#file").click());
  $("#bag").addEventListener("click", openBag);
  $("#file").addEventListener("change", (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    if (file) addPhoto(file);
  });

  panel.addEventListener("keydown", trapFocus);
  $("#panel-close").addEventListener("click", () => closePanel());
  $("#scrim").addEventListener("click", () => closePanel());
  $("#panel-body").addEventListener("click", (e) => {
    const sim = e.target.closest("[data-similar]");
    if (sim) openPanel(sim.dataset.similar);
    const give = e.target.closest("[data-donate]");
    if (give) donateItem(give.dataset.donate);
    const del = e.target.closest("[data-delete]");
    if (del) deleteItem(del.dataset.delete);
    const edit = e.target.closest("[data-edit]");
    if (edit) openPanel(edit.dataset.edit, null, { edit: true });
  });
}

async function init() {
  bind();
  try {
    await loadDuplicates();
    const data = await loadItems();
    refreshBagCount();
    $("#open-hint").textContent = data.total
      ? `${plural(data.total, "pièce")} vous ${data.total > 1 ? "attendent" : "attend"}`
      : "Votre garde-robe est vide : ajoutez une première pièce";
  } catch (e) {
    $("#open-hint").textContent = "API M1 indisponible";
    toast(`Impossible de charger la garde-robe : ${e.message}`, "error", { sticky: true });
  }
}

init();
