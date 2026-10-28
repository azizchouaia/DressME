// DressMe · M5 style profile demo. Vanilla JS, calls the M5 endpoints only (images come from M1 / M5).
// Flow: 10 swipes straight away (no question, no wardrobe analysis) -> daily batches of 10 (8 close to the
// taste + 2 "Découverte" cards); the style coach explains and adjusts the profile afterwards.
// Swipes are queued and sent in the background (batched POST /m05/feedback), like the mobile app will.

const API = "/m05";
const $ = (sel) => document.querySelector(sel);

const OCCASIONS = { work: "Travail", uni: "Université", casual: "Décontracté", event: "Événement", sport: "Sport" };
const STEPS = ["Swipes", "Quotidien"];

const S = {
  user: "usr_demo", styles: null, profile: null, lastMeta: "", queue: [], flushTimer: null, panelTimer: null, coachThread: null,
};

// --- tiny DOM helper (no innerHTML with data) --------------------------------------------------------
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") node.className = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (k === "style") node.style.cssText = v;
    else node.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) if (c !== null && c !== undefined && c !== false) node.append(c);
  return node;
}

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (t.hidden = true), 3200);
}

async function api(method, path, body) {
  const res = await fetch(API + path, {
    method, headers: body ? { "Content-Type": "application/json" } : {}, body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail || data);
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  return data;
}

const styleLabel = (id) => S.styles?.styles.find((s) => s.id === id)?.label || id;
const familyOf = (id) => S.styles?.styles.find((s) => s.id === id)?.family;
const familyLabel = (f) => S.styles?.families[f]?.label || f;
const familyColour = (f) => S.styles?.families[f]?.colour || "#999";
const pct = (x) => `${Math.round(x * 100)} %`;

// --- screens --------------------------------------------------------------------------------------------
function setStep(i) {
  $("#steps").replaceChildren(...STEPS.map((_, n) => el("span", { class: n <= i ? "on" : "" })));
}

function show(step, ...children) {
  setStep(step);
  $("#screen").replaceChildren(...children.flat().filter((c) => c !== null && c !== undefined));
}

function head(kicker, title, lead) {
  return [el("p", { class: "screen__kicker" }, kicker), el("h2", { class: "screen__title" }, title),
    lead ? el("p", { class: "screen__lead" }, lead) : null];
}

function bars(map, colourOf, labelOf) {
  return el("div", { class: "bars" }, Object.entries(map).filter(([, v]) => v > 0.005).slice(0, 6).map(([k, v]) =>
    el("div", { class: "bar" }, el("span", {}, labelOf(k)),
      el("span", { class: "bar__track" }, el("span", { class: "bar__fill", style: `width:${v * 100}%;background:${colourOf(k)}` })),
      el("span", { class: "bar__val" }, pct(v)))));
}

// --- swipe deck ------------------------------------------------------------------------------------------
function ctxBadges(c) {
  return el("div", { class: "card__ctx" },
    el("span", {}, `${c.rain ? "🌧" : c.temp_c >= 25 ? "☀️" : c.temp_c < 12 ? "❄️" : "⛅"} ${Math.round(c.temp_c)} °C`),
    el("span", {}, OCCASIONS[c.occasion] || c.occasion), el("span", {}, c.weekend ? "Week-end" : "Semaine"));
}

function cardNode(card) {
  const imgs = card.images.slice(0, 4);
  const media = el("div", { class: `card__media ${imgs.length === 1 ? "card__media--one" : imgs.length === 3 ? "card__media--three" : ""}` },
    imgs.map((src) => el("img", { src, alt: "", draggable: "false" })));
  const title = card.title || `Tenue · ${card.item_ids.length} pièces`;
  return el("article", { class: "card", "aria-label": title },
    media,
    el("div", { class: "card__body" }, ctxBadges(card.context),
      card.explore ? el("span", { class: "card__explore", title: "Un style différent du vôtre, pour découvrir" }, "Découverte") : null,
      el("h3", { class: "card__title" }, title),
      el("div", { class: "card__styles" }, card.top_styles.map((s) => el("span", {}, `${styleLabel(s.style)} ${pct(s.share)}`)))),
    el("span", { class: "card__stamp card__stamp--yes" }, "J'AIME"), el("span", { class: "card__stamp card__stamp--no" }, "NON"));
}

function deck(cards, { onboarding, onDone }) {
  cards.forEach((c) => c.images.forEach((src) => { const i = new Image(); i.src = src; }));    // preload the batch
  let index = 0;
  const liked = { n: 0 };
  const stack = el("div", { class: "deck" });
  const progress = el("div", { class: "progress" }, el("span", {}), el("span", {}));
  const why = el("div", { class: "why", hidden: true });
  const reactions = onboarding
    ? [["reject", "✕", "round--no", "Non (←)"], ["like", "♥", "round--heart", "J'aime (→)"]]
    : [["reject", "✕", "round--no", "Non (←)"], ["ignored", "↷", "round--small", "Passer (↓)"],
       ["accept", "✓", "round--yes", "Oui (→)"], ["heart", "♥", "round--heart", "Coup de cœur (↑)"]];
  const buttons = reactions.map(([r, icon, cls, label]) =>
    el("button", { class: `round ${cls}`, type: "button", title: label, "aria-label": label, onclick: () => decide(r) }, icon));
  const whyBtn = onboarding ? null : el("button", { class: "btn btn--ghost btn--sm", type: "button", onclick: explainCard }, "Pourquoi cette tenue ?");

  function render() {
    stack.replaceChildren();
    const rest = cards.slice(index, index + 2).reverse();
    rest.forEach((c, n) => {
      const node = cardNode(c);
      if (n === 0 && rest.length === 2) node.classList.add("is-back");
      stack.append(node);
    });
    if (index >= cards.length) stack.append(el("div", { class: "deck__empty" }, "Lot terminé."));
    else drag(stack.lastElementChild);
    progress.firstChild.textContent = `${Math.min(index + 1, cards.length)} / ${cards.length}`;
    progress.lastChild.textContent = `${liked.n} aimée${liked.n > 1 ? "s" : ""}`;
    buttons.forEach((b) => (b.disabled = index >= cards.length));
    if (whyBtn) whyBtn.disabled = index >= cards.length;
    why.hidden = true;
  }

  function decide(reaction) {
    if (index >= cards.length) return;
    const card = cards[index];
    const node = stack.querySelector(".card:not(.is-back)");
    node?.classList.add(reaction === "reject" ? "out-left" : reaction === "ignored" ? "out-up" : "out-right");
    if (["like", "accept", "heart"].includes(reaction)) liked.n += 1;
    enqueue({ log_id: card.log_id, reaction, source: onboarding ? "onboarding" : "swipe" });
    index += 1;
    setTimeout(() => (index >= cards.length ? onDone(liked.n, cards.length) : render()), 260);
  }

  async function explainCard() {
    const card = cards[index];
    try {
      await flush();
      const e = await api("GET", `/explain/${encodeURIComponent(S.user)}?log_id=${card.log_id}&k=4`);
      why.replaceChildren(el("strong", {}, "Ce qui a compté pour cette carte"),
        el("ul", {}, (e.card || []).map((r) => el("li", {}, `${r.weight >= 0 ? "＋" : "－"} ${r.label}`))));
      why.hidden = false;
    } catch (err) { toast(err.message); }
  }

  function drag(node) {
    let x0 = null, dx = 0, dy = 0, y0 = 0;
    const yes = node.querySelector(".card__stamp--yes"), no = node.querySelector(".card__stamp--no");
    node.addEventListener("pointerdown", (e) => { x0 = e.clientX; y0 = e.clientY; node.setPointerCapture(e.pointerId); node.classList.add("is-dragging"); });
    node.addEventListener("pointermove", (e) => {
      if (x0 === null) return;
      dx = e.clientX - x0; dy = e.clientY - y0;
      node.style.transform = `translate(${dx}px, ${Math.min(dy, 0) * 0.4}px) rotate(${dx / 18}deg)`;
      yes.style.opacity = String(Math.max(0, Math.min(1, dx / 90)));
      no.style.opacity = String(Math.max(0, Math.min(1, -dx / 90)));
    });
    const end = () => {
      if (x0 === null) return;
      x0 = null;
      node.classList.remove("is-dragging");
      node.style.transform = "";
      yes.style.opacity = no.style.opacity = "0";
      if (dx > 90) decide(onboarding ? "like" : "accept");
      else if (dx < -90) decide("reject");
      else if (!onboarding && dy < -110) decide("heart");
      dx = dy = 0;
    };
    node.addEventListener("pointerup", end);
    node.addEventListener("pointercancel", end);
  }

  const onKey = (e) => {
    if (!stack.isConnected) return document.removeEventListener("keydown", onKey);
    if (["INPUT", "SELECT"].includes(document.activeElement?.tagName)) return;
    const map = onboarding ? { ArrowLeft: "reject", ArrowRight: "like" }
      : { ArrowLeft: "reject", ArrowRight: "accept", ArrowUp: "heart", ArrowDown: "ignored" };
    if (map[e.key]) { e.preventDefault(); decide(map[e.key]); }
  };
  document.addEventListener("keydown", onKey);
  render();
  return el("div", { style: "display:flex;flex-direction:column;gap:14px" }, progress, stack,
    el("div", { class: "actions" }, buttons), whyBtn, why);
}

async function screenSwipes() {
  show(0, ...head("Votre style", "Chargement des cartes…"));
  let r;
  try { r = await api("GET", `/onboarding/swipe-cards?user_id=${encodeURIComponent(S.user)}`); } catch (e) { return toast(e.message); }
  S.lastMeta = `${r.n_candidates} candidats (${r.candidates_source}) · ${r.elapsed_ms} ms côté serveur`;
  refreshPanel();
  show(0, ...head(`Votre style · ${r.cards.length} cartes`, "Ce look vous plaît ?",
    "Aucune question : swipez à droite ce que vous aimez, à gauche le reste. Votre profil se construit à chaque swipe."),
  deck(r.cards, { onboarding: true, onDone: (n, total) => {
    show(0, ...head("Merci !", `${n} carte${n > 1 ? "s" : ""} aimée${n > 1 ? "s" : ""} sur ${total}.`,
      "Votre profil est prêt. Place aux suggestions du jour."),
    el("div", { class: "screen__actions" }, el("button", { class: "btn btn--block", onclick: screenDaily }, "Voir mes tenues du jour")));
  } }));
}

const DAILY = { temp_c: 22, rain: false, occasion: "work", weekend: false };

function screenDaily() {
  const temp = el("input", { type: "range", min: "-5", max: "42", step: "1", value: String(DAILY.temp_c), "aria-label": "Température" });
  const tempOut = el("span", {}, `${DAILY.temp_c} °C`);
  temp.addEventListener("input", () => { DAILY.temp_c = Number(temp.value); tempOut.textContent = `${DAILY.temp_c} °C`; });
  const occ = el("select", { "aria-label": "Occasion" }, Object.entries(OCCASIONS).map(([k, l]) => el("option", { value: k, selected: k === DAILY.occasion }, l)));
  occ.addEventListener("change", () => (DAILY.occasion = occ.value));
  const rain = el("input", { type: "checkbox", checked: DAILY.rain });
  rain.addEventListener("change", () => (DAILY.rain = rain.checked));
  const weekend = el("input", { type: "checkbox", checked: DAILY.weekend });
  weekend.addEventListener("change", () => (DAILY.weekend = weekend.checked));
  const area = el("div", {});
  const load = async () => {
    area.replaceChildren(el("p", { class: "note" }, "Classement en cours…"));
    try {
      const r = await api("POST", "/choose", { user_id: S.user, context: { ...DAILY } });
      S.lastMeta = `${r.n_candidates} tenues candidates (${r.candidates_source}) → ${r.cards.length} cartes · ${r.elapsed_ms} ms côté serveur`;
      refreshPanel();
      if (!r.cards.length) return area.replaceChildren(el("p", { class: "note" }, "Aucune tenue possible avec cette garde-robe et ce contexte."));
      area.replaceChildren(deck(r.cards, { onboarding: false, onDone: (n, total) => {
        area.replaceChildren(el("p", { class: "note" }, `${n} / ${total} tenues aimées dans ce lot.`),
          el("button", { class: "btn btn--block", onclick: load }, "10 tenues de plus"));
      } }));
    } catch (e) { area.replaceChildren(el("p", { class: "error" }, e.message)); }
  };
  show(1, ...head("Suggestions du jour", "Vos 10 tenues"),
    el("div", { class: "ctx" },
      el("label", { class: "field field--wide" }, el("span", { class: "field__label" }, "Météo (fournie par le client pour l'instant)"),
        el("div", { class: "slider", style: "padding:4px 0" }, temp, el("div", { class: "slider__ends" }, el("span", {}, "-5 °C"), tempOut, el("span", {}, "42 °C")))),
      el("label", { class: "field" }, el("span", { class: "field__label" }, "Occasion"), occ),
      el("div", { class: "field", style: "justify-content:flex-end;gap:8px" },
        el("label", { class: "toggle" }, rain, "Pluie"), el("label", { class: "toggle" }, weekend, "Week-end"))),
    el("button", { class: "btn btn--block", onclick: load }, "Obtenir 10 tenues"), area);
}

// --- background feedback queue ---------------------------------------------------------------------------
function enqueue(event) {
  S.queue.push(event);
  clearTimeout(S.flushTimer);
  S.flushTimer = setTimeout(flush, S.queue.length >= 5 ? 0 : 900);
}

async function flush() {
  clearTimeout(S.flushTimer);
  if (!S.queue.length) return;
  const events = S.queue.splice(0, S.queue.length);
  try {
    await api("POST", "/feedback", { user_id: S.user, events });
    schedulePanel();
  } catch (e) {
    if (e.status >= 500 || !e.status) { S.queue.unshift(...events); S.flushTimer = setTimeout(flush, 3000); }
    else toast(`Retour refusé : ${e.message}`);
  }
}

window.addEventListener("pagehide", () => {
  if (S.queue.length) {
    navigator.sendBeacon(`${API}/feedback`, new Blob([JSON.stringify({ user_id: S.user, events: S.queue })], { type: "application/json" }));
    S.queue = [];
  }
});

function showCoach(on) {   // the floating coach needs a profile learnt from the first swipes
  $("#coach-open").hidden = !on;
  if (!on) $("#coach").hidden = true;
}

// --- side panel ------------------------------------------------------------------------------------------
function schedulePanel() { clearTimeout(S.panelTimer); S.panelTimer = setTimeout(refreshPanel, 250); }

async function refreshPanel() {
  let p, e;
  try {
    [p, e] = await Promise.all([api("GET", `/profile/${encodeURIComponent(S.user)}`), api("GET", `/explain/${encodeURIComponent(S.user)}?k=5`)]);
  } catch {
    $("#panel-empty").hidden = false; $("#panel-body").hidden = true;
    showCoach(false);
    $("#badge-feedback").textContent = "0 retour";
    $("#meta").textContent = S.lastMeta;
    return;
  }
  S.profile = p;
  showCoach(p.onboarded);
  $("#panel-empty").hidden = true; $("#panel-body").hidden = false;
  $("#badge-feedback").textContent = `${p.n_feedback} retour${p.n_feedback > 1 ? "s" : ""}`;
  $("#families").replaceChildren(bars(p.families, familyColour, familyLabel));
  $("#top-styles").replaceChildren(...p.top_styles.map((s) =>
    el("span", { class: "chip chip--static" }, el("span", { class: "swatch", style: `background:${familyColour(s.family)}` }), `${styleLabel(s.style)} · ${pct(s.share)}`)));
  const rule = (r) => el("li", {}, el("span", {}, r.label),
    el("small", {}, `${r.weight >= 0 ? "+" : ""}${r.weight.toFixed(2)}${r.uncertainty == null ? "" : ` ± ${r.uncertainty.toFixed(2)}`}`));
  $("#rules-pos").replaceChildren(...e.positive.map(rule));
  $("#rules-neg").replaceChildren(...e.negative.map(rule));
  const a = p.answers;
  const styles = (ids) => (ids || []).map(styleLabel).join(", ") || "—";
  $("#facts").replaceChildren(
    el("dt", {}, "Onboarding"), el("dd", {}, p.onboarded ? "terminé" : "en cours"),
    el("dt", {}, "Envie de plus"), el("dd", {}, styles(a.want_more)),
    el("dt", {}, "Envie de moins"), el("dd", {}, styles(a.want_less)),
    el("dt", {}, "Vecteur de goût"), el("dd", {}, p.taste_vector ? `${p.taste_vector.length} dimensions` : "après le premier « j'aime »"));
  $("#meta").textContent = [S.lastMeta, `liste de styles ${p.styles_version} · ${S.styles.styles.length} styles · DIM ${S.styles.dim}`].filter(Boolean).join(" — ");
}

// --- style coach agent ---------------------------------------------------------------------------------------
const TOOL_FR = {
  get_style_profile: "lit le profil", explain_my_recommendations: "explique les règles apprises",
  update_style_preferences: "met à jour le profil", recommend_outfits: "choisit des tenues",
};

function bubble(log, who, ...children) {
  const node = el("div", { class: `bubble bubble--${who}` }, ...children);
  log.append(node);
  node.scrollIntoView({ block: "end", behavior: "smooth" });
  return node;
}

function miniCard(card) {
  return el("figure", { class: "mini" },
    el("div", { class: "mini__media" }, card.images.slice(0, 4).map((src) => el("img", { src, alt: "" }))),
    el("figcaption", {}, card.top_styles.slice(0, 2).map((s) => `${styleLabel(s.style)} ${pct(s.share)}`).join(" · ")));
}

// ui = { log, input, key (thread field of S), onResult(r, node) }
async function chatSend(ui, message) {
  bubble(ui.log, "user", message);
  const wait = bubble(ui.log, "bot", el("span", { class: "dots" }, "Le coach réfléchit"));
  ui.input.disabled = true;
  try {
    const r = await api("POST", "/agent/chat", { user_id: S.user, message, thread_id: S[ui.key] });
    S[ui.key] = r.thread_id;
    $("#coach-model").textContent = `Agent M5 · ${r.model} · ${(r.elapsed_ms / 1000).toFixed(1)} s`;
    wait.replaceChildren(...[   // replaceChildren(null) would print "null": keep real nodes only
      r.steps.length ? el("ol", { class: "steps" }, r.steps.map((s) =>
        el("li", { title: s.result }, el("code", {}, s.tool), ` ${TOOL_FR[s.tool] || ""}`))) : null,
      el("p", {}, r.reply),
      r.cards.length ? el("div", { class: "minis" }, r.cards.map(miniCard)) : null].filter(Boolean));
    if (r.profile_changed) refreshPanel();
    ui.onResult?.(r, wait);
  } catch (e) {
    wait.replaceChildren(el("p", { class: "bubble__error" },
      e.status === 503 ? "Le LLM local ne répond pas : lancez Ollama (et le modèle) puis réessayez." : e.message));
  } finally {
    ui.input.disabled = false;
    ui.input.focus();
  }
}

function bindChatForm(form, ui) {
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const msg = ui.input.value.trim();
    if (!msg || ui.input.disabled) return;
    ui.input.value = "";
    chatSend(ui, msg);
  });
  return form;
}

// after onboarding: the floating coach explains and adjusts the profile
function setupCoach() {
  const ui = {
    log: $("#coach-log"), input: $("#coach-input"), key: "coachThread",
    onResult: (r) => { if (r.profile_changed) toast("Profil mis à jour par le coach."); },
  };
  const open = (on) => { $("#coach").hidden = !on; $("#coach-open").setAttribute("aria-expanded", String(on)); if (on) ui.input.focus(); };
  $("#coach-open").addEventListener("click", () => open($("#coach").hidden));
  $("#coach-close").addEventListener("click", () => open(false));
  $("#coach-new").addEventListener("click", coachReset);
  bindChatForm($("#coach-form"), ui);
}

function coachReset() {
  S.coachThread = null;
  $("#coach-log").replaceChildren($("#coach-log").firstElementChild);
}

// --- boot ------------------------------------------------------------------------------------------------
async function openUser(user) {
  await flush();
  if (user !== S.user) coachReset();
  S.user = user;
  S.lastMeta = "";
  history.replaceState(null, "", `?user=${encodeURIComponent(user)}`);
  $("#user-id").value = user;
  try {
    S.profile = await api("GET", `/profile/${encodeURIComponent(user)}`);
  } catch { S.profile = null; }
  refreshPanel();
  if (S.profile?.onboarded) screenDaily(); else screenSwipes();   // no question before the first swipes
}

async function boot() {
  try {
    S.styles = await api("GET", "/styles");
  } catch (e) { return toast(`M5 indisponible : ${e.message}`); }
  setupCoach();
  $("#userbar").addEventListener("submit", (e) => { e.preventDefault(); openUser($("#user-id").value.trim() || "usr_demo"); });
  $("#reset").addEventListener("click", async () => {
    if (!confirm(`Effacer le profil M5 de ${S.user} (profil, bandit, historique) ? Les pièces M1 ne sont pas touchées.`)) return;
    S.queue = [];
    try { await api("DELETE", `/profile/${encodeURIComponent(S.user)}`); } catch { /* nothing to delete */ }
    openUser(S.user);
  });
  openUser(new URLSearchParams(location.search).get("user") || "usr_demo");
}

boot();
