import { useState } from "react";

type Category = "Tous" | "Hauts" | "Bas" | "Robes" | "Chaussures" | "Accessoires" | "Vestes";

const categories: Category[] = ["Tous", "Hauts", "Bas", "Robes", "Chaussures", "Accessoires", "Vestes"];
const clothes = [
  { id: 1, name: "Chemise blanche", category: "Hauts", times: 8, image: "https://images.unsplash.com/photo-1556630184-066f7ac4e15f?w=500&h=600&fit=crop&auto=format" },
  { id: 2, name: "Jean bleu droit", category: "Bas", times: 12, image: "https://images.unsplash.com/photo-1542272604-787c3835535d?w=500&h=600&fit=crop&auto=format" },
  { id: 3, name: "Robe midi beige", category: "Robes", times: 3, image: "https://images.unsplash.com/photo-1616639943825-e0fbad20a3d3?w=500&h=600&fit=crop&auto=format" },
  { id: 4, name: "Blazer camel", category: "Vestes", times: 6, image: "https://images.unsplash.com/photo-1551232864-3f0890e580d9?w=500&h=600&fit=crop&auto=format" },
  { id: 5, name: "Baskets blanches", category: "Chaussures", times: 15, image: "https://images.unsplash.com/photo-1549298916-b41d501d3772?w=500&h=600&fit=crop&auto=format" },
  { id: 6, name: "Pull crème", category: "Hauts", times: 5, image: "https://images.unsplash.com/photo-1576566588028-4147f3842f27?w=500&h=600&fit=crop&auto=format" },
];

const outfitLooks = [
  "https://images.unsplash.com/photo-1529399447871-731cff7f696b?w=400&h=520&fit=crop&auto=format",
  "https://images.unsplash.com/photo-1597308784057-ea6c4e17bfa4?w=400&h=520&fit=crop&auto=format",
  "https://images.unsplash.com/photo-1693611282973-f2aace989928?w=400&h=520&fit=crop&auto=format",
  "https://images.unsplash.com/photo-1700746709309-8d5c008a72dd?w=400&h=520&fit=crop&auto=format",
];

const gaps = [
  { name: "Baskets blanches", count: 14, width: "100%" },
  { name: "Trench beige", count: 9, width: "64%" },
  { name: "Ceinture marron", count: 6, width: "43%" },
];

export default function WardrobeScreen() {
  const [activeCategory, setActiveCategory] = useState<Category>("Tous");
  const [selected, setSelected] = useState<(typeof clothes)[number] | null>(null);
  const [showGaps, setShowGaps] = useState(false);
  const [capsule, setCapsule] = useState(false);
  const [declutter, setDeclutter] = useState(false);
  const [declutterIndex, setDeclutterIndex] = useState(0);
  const [importing, setImporting] = useState(false);
  const filtered = activeCategory === "Tous" ? clothes : clothes.filter((item) => item.category === activeCategory);

  return (
    <div className="min-h-full bg-[#F6F3EE] pb-8">
      <section className="bg-[#211D19] px-5 pb-7 pt-7 text-white">
        <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[#C9A77B]">Ton vrai placard</p>
        <div className="mt-1 flex items-end justify-between">
          <div><h1 className="font-serif text-[34px]">Garde-robe</h1><p className="mt-1 text-[12px] text-white/50">64 pièces · 18 hauts · 9 bas · 7 paires</p></div>
          <button className="h-11 w-11 rounded-full border border-white/15 bg-white/10 text-xl">+</button>
        </div>
      </section>

      <div className="sticky top-0 z-20 flex gap-2 overflow-x-auto bg-[#F6F3EE]/95 px-4 py-4 backdrop-blur no-scrollbar">
        {categories.map((category) => (
          <button key={category} onClick={() => setActiveCategory(category)} className={`shrink-0 rounded-full px-4 py-2 text-[11px] font-semibold ${activeCategory === category ? "bg-[#211D19] text-white" : "border border-[#DED5C9] bg-white text-[#71685F]"}`}>{category}</button>
        ))}
      </div>

      <div className="px-4">
        <div className="mb-3 grid grid-cols-2 gap-3">
          <button onClick={() => setCapsule(!capsule)} className={`rounded-2xl p-4 text-left ${capsule ? "bg-[#211D19] text-white" : "border border-[#E2D8CC] bg-white"}`}>
            <span className={`block text-[9px] font-bold uppercase tracking-wider ${capsule ? "text-[#C9A77B]" : "text-[#9A744B]"}`}>Mode capsule</span>
            <span className="mt-1 block text-[12px] font-semibold">{capsule ? "15 pièces = 48 tenues" : "Créer ma capsule"}</span>
          </button>
          <button onClick={() => setDeclutter(true)} className="rounded-2xl border border-[#E2D8CC] bg-white p-4 text-left">
            <span className="block text-[9px] font-bold uppercase tracking-wider text-[#9A744B]">Anti-gaspillage</span>
            <span className="mt-1 block text-[12px] font-semibold">Désencombrer</span>
          </button>
        </div>

        <button onClick={() => { setImporting(true); window.setTimeout(() => setImporting(false), 1300); }} className="mb-3 flex w-full items-center justify-between rounded-2xl border border-[#E2D8CC] bg-white p-4 text-left">
          <span><span className="block text-[9px] font-bold uppercase tracking-wider text-[#9A744B]">Ajout intelligent</span><span className="mt-1 block text-[12px] font-semibold">{importing ? "Classement automatique de 20 photos…" : "Importer et classer 20 photos"}</span></span>
          <span className="text-[11px] text-[#81776D]">{importing ? "68 %" : "T-shirt · blanc · été"}</span>
        </button>

        <div className="mb-3 rounded-2xl border border-[#D7E5DA] bg-[#EFF7F1] p-4">
          <div className="flex items-center justify-between"><div><span className="block text-[9px] font-bold uppercase tracking-wider text-[#447255]">Impact du placard</span><span className="font-serif text-[19px] text-[#294C35]">Score durable : 68</span></div><div className="flex h-12 w-12 items-center justify-center rounded-full border-4 border-[#5E9671] bg-white text-[12px] font-bold text-[#294C35]">68</div></div>
          <p className="mt-2 text-[10px] text-[#587060]">11 pièces remises en rotation · 3 achats évités ce mois</p>
        </div>

        <button onClick={() => setShowGaps(!showGaps)} className="mb-5 flex w-full items-center justify-between rounded-2xl bg-[#C9A77B] p-4 text-left text-[#211D19]">
          <span><span className="block text-[10px] font-bold uppercase tracking-wider opacity-60">Analyse IA</span><span className="font-serif text-[19px]">Ce qui manque à ta garde-robe</span></span>
          <span className="text-xl">{showGaps ? "−" : "+"}</span>
        </button>
        {showGaps && (
          <div className="-mt-3 mb-5 rounded-2xl border border-[#E2D8CC] bg-white p-4">
            {gaps.map((gap) => (
              <div key={gap.name} className="mb-4 last:mb-0">
                <div className="mb-1.5 flex justify-between text-[12px]"><span className="font-semibold">{gap.name}</span><span className="text-[#9A744B]">+{gap.count} tenues</span></div>
                <div className="h-1.5 overflow-hidden rounded-full bg-[#EFEAE3]"><div className="h-full rounded-full bg-[#B78C5B]" style={{ width: gap.width }} /></div>
              </div>
            ))}
          </div>
        )}

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {filtered.map((item, index) => (
            <button key={item.id} onClick={() => setSelected(item)} className={`overflow-hidden rounded-2xl border border-[#E5DED4] bg-white text-left shadow-sm ${capsule && index > 2 ? "opacity-35 grayscale" : ""}`}>
              <div className="relative h-48"><img src={item.image} alt={item.name} className="h-full w-full object-cover" /><span className="absolute right-2 top-2 rounded-full bg-white/90 px-2 py-1 text-[9px] font-bold">porté {item.times}×</span></div>
              <div className="p-3"><p className="text-[12px] font-semibold">{item.name}</p><p className="mt-1 text-[10px] text-[#8A8076]">{item.category}</p></div>
            </button>
          ))}
        </div>
      </div>

      {selected && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-[#F6F3EE]">
          <div className="mx-auto max-w-2xl pb-8">
            <div className="relative h-[390px]">
              <img src={selected.image} alt={selected.name} className="h-full w-full object-cover" />
              <div className="absolute inset-0 bg-gradient-to-t from-[#F6F3EE] via-transparent to-black/20" />
              <button onClick={() => setSelected(null)} className="absolute left-4 top-4 h-11 w-11 rounded-full bg-white/90 text-lg shadow">←</button>
            </div>
            <div className="-mt-8 relative px-5">
              <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#9A744B]">{selected.category} · Dans ta garde-robe</p>
              <h2 className="mt-1 font-serif text-[31px]">{selected.name}</h2>
              <div className="mt-4 grid grid-cols-3 gap-2 rounded-2xl border border-[#E2D8CC] bg-white p-4 text-center">
                <div><b className="block text-[18px]">23</b><span className="text-[9px] text-[#81776D]">fois portée</span></div>
                <div><b className="block text-[18px]">4 j</b><span className="text-[9px] text-[#81776D]">dernier port</span></div>
                <div><b className="block text-[18px]">6,5</b><span className="text-[9px] text-[#81776D]">TND / port</span></div>
              </div>
              <div className="mb-3 mt-7 flex items-end justify-between"><div><p className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#9A744B]">100 % tes vêtements</p><h3 className="font-serif text-[24px]">Utilisée dans 12 tenues</h3></div><span className="text-[11px] text-[#81776D]">Faire défiler →</span></div>
              <div className="flex gap-3 overflow-x-auto pb-3 no-scrollbar">
                {outfitLooks.map((image, index) => (
                  <article key={image} className="w-[150px] shrink-0 overflow-hidden rounded-2xl bg-white">
                    <img src={image} alt={`Tenue ${index + 1} avec ${selected.name}`} className="h-48 w-full object-cover" />
                    <div className="p-3"><p className="text-[11px] font-semibold">{["Campus casual", "Café en ville", "Vendredi chic", "Week-end doux"][index]}</p><p className="text-[9px] text-[#9A744B]">Depuis ton placard</p></div>
                  </article>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {declutter && (
        <div className="fixed inset-0 z-50 flex items-end bg-black/50" onClick={() => setDeclutter(false)}>
          <div className="mx-auto w-full max-w-xl rounded-t-[30px] bg-[#F6F3EE] p-5" onClick={(event) => event.stopPropagation()}>
            <div className="mb-4 flex items-start justify-between"><div><p className="text-[10px] font-bold uppercase tracking-wider text-[#9A744B]">Revue {declutterIndex + 1}/3</p><h3 className="font-serif text-[25px]">Cette pièce te sert-elle encore ?</h3></div><button onClick={() => setDeclutter(false)} className="h-9 w-9 rounded-full bg-white">×</button></div>
            <img src={clothes[(declutterIndex + 3) % clothes.length].image} alt="Pièce à revoir" className="h-72 w-full rounded-2xl object-cover" />
            <div className="my-4 rounded-xl bg-[#FFF1DF] p-3 text-[11px] text-[#765A3C]">{declutterIndex === 0 ? "3 vestes très proches dans ta garde-robe" : declutterIndex === 1 ? "Pas portée depuis 8 mois" : "Éloignée de ton style actuel"}</div>
            <div className="grid grid-cols-2 gap-3"><button onClick={() => setDeclutterIndex((declutterIndex + 1) % 3)} className="rounded-2xl border border-[#DED5C9] bg-white py-3.5 text-[12px] font-semibold">Garder</button><button onClick={() => setDeclutterIndex((declutterIndex + 1) % 3)} className="rounded-2xl bg-[#211D19] py-3.5 text-[12px] font-semibold text-white">Donner à Tunis</button></div>
            <p className="mt-3 text-center text-[9px] text-[#81776D]">Point de collecte le plus proche : Association El Amen · 1,2 km</p>
          </div>
        </div>
      )}
    </div>
  );
}
