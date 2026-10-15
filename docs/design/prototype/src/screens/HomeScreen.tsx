import { useState } from "react";

type Tab = "home" | "wardrobe" | "recommendations" | "assistant" | "profile";

interface Props {
  onTabChange: (tab: Tab) => void;
}

const outfits = [
  {
    name: "Campus en douceur",
    score: 96,
    image: "https://images.unsplash.com/photo-1762605135318-f34a993cbcf0?w=900&h=1100&fit=crop&auto=format",
    pieces: ["Chemise crème", "Jean marine", "Baskets blanches"],
  },
  {
    name: "Minimaliste solaire",
    score: 93,
    image: "https://images.unsplash.com/photo-1529399447871-731cff7f696b?w=900&h=1100&fit=crop&auto=format",
    pieces: ["Top beige", "Pantalon noir", "Sac camel"],
  },
  {
    name: "Casual structuré",
    score: 91,
    image: "https://images.unsplash.com/photo-1693611282973-f2aace989928?w=900&h=1100&fit=crop&auto=format",
    pieces: ["Veste kaki", "T-shirt blanc", "Jean droit"],
  },
];

const alternatives = [
  { name: "Tons terre", image: "https://images.unsplash.com/photo-1597308784057-ea6c4e17bfa4?w=400&h=500&fit=crop&auto=format" },
  { name: "Marine épuré", image: "https://images.unsplash.com/photo-1700746709309-8d5c008a72dd?w=400&h=500&fit=crop&auto=format" },
];

const localPieces = [
  { name: "Chemise en lin", shop: "Lyoum · La Marsa", price: "89 TND", match: "92 %", image: "https://images.unsplash.com/photo-1603252109303-2751441dd157?w=360&h=420&fit=crop&auto=format" },
  { name: "Sac artisanal", shop: "Kenenti · Tunis", price: "120 TND", match: "89 %", image: "https://images.unsplash.com/photo-1559563458-527698bf5295?w=360&h=420&fit=crop&auto=format" },
  { name: "Veste sable", shop: "Anissa Aida · Tunis", price: "245 TND", match: "87 %", image: "https://images.unsplash.com/photo-1551488831-00ddcb6c6bd3?w=360&h=420&fit=crop&auto=format" },
  { name: "Mocassins cuir", shop: "Dorra · Sfax", price: "135 TND", match: "84 %", image: "https://images.unsplash.com/photo-1543163521-1bf539c55dd2?w=360&h=420&fit=crop&auto=format" },
  { name: "Foulard tissé", shop: "Khomsa · Sousse", price: "48 TND", match: "82 %", image: "https://images.unsplash.com/photo-1601924994987-69e26d50dc26?w=360&h=420&fit=crop&auto=format" },
];

export default function HomeScreen({ onTabChange }: Props) {
  const [occasion, setOccasion] = useState("Université");
  const [outfitIndex, setOutfitIndex] = useState(0);
  const [remixing, setRemixing] = useState(false);
  const [showWhy, setShowWhy] = useState(false);
  const [feedback, setFeedback] = useState(false);
  const [toast, setToast] = useState("");
  const [chatOpen, setChatOpen] = useState(false);
  const [chatSent, setChatSent] = useState(false);
  const [cameraOpen, setCameraOpen] = useState(false);

  const outfit = outfits[outfitIndex];

  const nextOutfit = (message?: string) => {
    setRemixing(true);
    setFeedback(false);
    window.setTimeout(() => {
      setOutfitIndex((current) => (current + 1) % outfits.length);
      setRemixing(false);
      if (message) {
        setToast(message);
        window.setTimeout(() => setToast(""), 2200);
      }
    }, 360);
  };

  return (
    <div className="min-h-full bg-[#F6F3EE] pb-8">
      <section className="relative overflow-hidden bg-[#171512] px-5 pb-8 pt-7 text-white">
        <div className="absolute -right-16 -top-20 h-64 w-64 rounded-full bg-[#9C7650]/25 blur-3xl" />
        <div className="relative">
          <div className="mb-5 flex items-start justify-between">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#CDB18D]">Lundi 14 septembre</p>
              <h1 className="mt-1 font-serif text-[34px] leading-none">Bonjour, Camille</h1>
            </div>
            <button onClick={() => setChatOpen(true)} aria-label="Ouvrir le styliste IA" className="flex h-11 w-11 items-center justify-center rounded-full border border-white/20 bg-white/10 text-lg">✦</button>
          </div>

          <div className="mb-5 flex items-center justify-between rounded-2xl border border-white/10 bg-white/8 px-4 py-3 backdrop-blur-md">
            <div>
              <p className="text-[11px] text-white/50">Tunis · Ensoleillé</p>
              <p className="text-[25px] font-semibold">24 °C</p>
            </div>
            <div className="text-right">
              <p className="text-[11px] text-white/50">Idéal aujourd’hui</p>
              <p className="text-[13px] font-medium text-[#E3C9A7]">Matières légères</p>
            </div>
          </div>

          <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-white/50">Pour quelle occasion ?</p>
          <div className="flex gap-2 overflow-x-auto no-scrollbar">
            {["Université", "Travail", "Sortie", "Dîner", "Mariage"].map((item) => (
              <button
                key={item}
                onClick={() => setOccasion(item)}
                className={`shrink-0 rounded-full px-4 py-2 text-[12px] font-semibold transition ${occasion === item ? "bg-[#C9A77B] text-[#171512]" : "border border-white/15 bg-white/5 text-white/65"}`}
              >
                {item}
              </button>
            ))}
          </div>
        </div>
      </section>

      <main className="-mt-3 px-4">
        <div className={`overflow-hidden rounded-[28px] border border-[#E5DED4] bg-white shadow-[0_18px_50px_rgba(45,35,25,0.12)] ${remixing ? "card-remix" : ""}`}>
          <div className="relative h-[360px] overflow-hidden">
            <img src={outfit.image} alt={outfit.name} className="h-full w-full object-cover" />
            <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/5 to-transparent" />
            <div className="absolute left-4 top-4 flex gap-2">
              <span className="rounded-full bg-[#171512]/75 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-white backdrop-blur">Adaptée à toi</span>
              {outfitIndex === 2 && <span className="rounded-full bg-[#C9A77B] px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-[#171512]">Rediscover</span>}
            </div>
            <div className="absolute bottom-5 left-5 right-5">
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#DFC39E]">{occasion} · Dans ton placard</p>
              <div className="flex items-end justify-between">
                <h2 className="font-serif text-[29px] leading-none text-white">{outfit.name}</h2>
                <div className="rounded-full border border-white/20 bg-white/15 px-3 py-1.5 text-[12px] font-bold text-white backdrop-blur">IA {outfit.score}%</div>
              </div>
            </div>
          </div>

          <div className="p-5">
            <div className="mb-4 flex flex-wrap gap-2">
              {outfit.pieces.map((piece, index) => (
                <span key={piece} className="rounded-full bg-[#F4F0EA] px-3 py-1.5 text-[11px] font-medium text-[#675F57]">
                  {piece}{outfitIndex === 2 && index === 0 ? " · pas portée depuis 74 jours" : ""}
                </span>
              ))}
            </div>

            <div className="grid grid-cols-[1fr_1fr_auto] gap-2">
              <button onClick={() => setToast("Tenue ajoutée à ton journal")} className="rounded-2xl bg-[#171512] py-3.5 text-[13px] font-semibold text-white">Je la porte</button>
              <button onClick={() => nextOutfit("Nouvelle combinaison créée")} className="rounded-2xl bg-[#C9A77B] py-3.5 text-[13px] font-semibold text-[#171512]">Remix</button>
              <button onClick={() => setFeedback(true)} aria-label="Cette tenue ne me plaît pas" className="rounded-2xl border border-[#E5DED4] px-4 text-[#675F57]">↓</button>
            </div>

            {feedback && (
              <div className="mt-4 rounded-2xl bg-[#F6F3EE] p-3">
                <p className="mb-2 text-[12px] font-semibold text-[#2A2520]">Qu’est-ce qui ne va pas ?</p>
                <div className="flex flex-wrap gap-2">
                  {["Trop formel", "Couleurs", "Pas la météo"].map((reason) => (
                    <button key={reason} onClick={() => nextOutfit("Noté, je m’adapte")} className="rounded-full border border-[#D9CEC0] bg-white px-3 py-1.5 text-[11px] text-[#675F57]">{reason}</button>
                  ))}
                </div>
              </div>
            )}

            <button onClick={() => setShowWhy(!showWhy)} className="mt-4 flex w-full items-center justify-between border-t border-[#EEE8E0] pt-4 text-left text-[12px] font-semibold text-[#2A2520]">
              <span>Pourquoi cette tenue ?</span><span>{showWhy ? "−" : "+"}</span>
            </button>
            {showWhy && (
              <div className="mt-3 space-y-2">
                {["Palette · Le beige et le marine s’accordent", "Météo · Adaptée à 24 °C", "Style · Proche de ton style casual"].map((reason) => (
                  <p key={reason} className="flex items-center gap-2 text-[12px] text-[#675F57]"><span className="text-[#B78C5B]">◆</span>{reason}</p>
                ))}
              </div>
            )}
          </div>
        </div>

        <section className="py-6">
          <div className="mb-3 flex items-end justify-between">
            <div><p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#A27B50]">Autres options</p><h2 className="font-serif text-[24px] text-[#211D19]">Deux autres idées</h2></div>
            <button onClick={() => onTabChange("recommendations")} className="text-[11px] font-semibold text-[#8D6842]">Ouvrir Studio</button>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {alternatives.map((item, index) => (
              <button key={item.name} onClick={() => setOutfitIndex(index + 1)} className="relative h-40 overflow-hidden rounded-2xl text-left">
                <img src={item.image} alt={item.name} className="h-full w-full object-cover" />
                <div className="absolute inset-0 bg-gradient-to-t from-black/70 to-transparent" />
                <span className="absolute bottom-3 left-3 text-[13px] font-semibold text-white">{item.name}</span>
              </button>
            ))}
          </div>
        </section>

        <section>
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#A27B50]">Sélection locale</p>
          <h2 className="mb-3 font-serif text-[24px] text-[#211D19]">Choisi pour toi en Tunisie</h2>
          <div className="flex gap-3 overflow-x-auto pb-3 no-scrollbar">
            {localPieces.map((piece) => (
              <article key={piece.name} className="w-[155px] shrink-0 overflow-hidden rounded-2xl border border-[#E5DED4] bg-white">
                <img src={piece.image} alt={piece.name} className="h-36 w-full object-cover" />
                <div className="p-3">
                  <p className="text-[12px] font-semibold text-[#211D19]">{piece.name}</p>
                  <p className="mt-0.5 text-[10px] text-[#81776D]">{piece.shop}</p>
                  <div className="mt-2 flex items-end justify-between"><span className="text-[11px] font-bold">{piece.price}</span><span className="text-[9px] text-[#A27B50]">{piece.match} proche</span></div>
                </div>
              </article>
            ))}
          </div>
        </section>
      </main>

      <button onClick={() => setCameraOpen(true)} aria-label="Photographier une pièce" className="fixed bottom-20 right-4 z-30 flex h-14 w-14 items-center justify-center rounded-full border-4 border-[#F6F3EE] bg-[#171512] text-xl text-white shadow-xl">◎</button>

      {toast && <div className="fixed bottom-24 left-1/2 z-[70] -translate-x-1/2 whitespace-nowrap rounded-full bg-[#211D19] px-4 py-2.5 text-[12px] font-semibold text-white shadow-xl">{toast}</div>}

      {chatOpen && (
        <div className="fixed inset-0 z-50 flex items-end bg-black/40" onClick={() => setChatOpen(false)}>
          <div className="mx-auto w-full max-w-xl rounded-t-[28px] bg-[#F6F3EE] p-5" onClick={(event) => event.stopPropagation()}>
            <div className="mb-5 flex items-center justify-between"><div><p className="text-[10px] uppercase tracking-widest text-[#A27B50]">Styliste IA</p><h3 className="font-serif text-[23px]">Demande-moi une tenue</h3></div><button onClick={() => setChatOpen(false)} className="h-9 w-9 rounded-full bg-white">×</button></div>
            <div className="mb-3 rounded-2xl bg-white p-4 text-[13px] text-[#4F4841]">Quel est ton programme ? Je prends en compte ta garde-robe et la météo.</div>
            {chatSent && (
              <div className="mb-3">
                <div className="ml-auto mb-3 w-fit rounded-2xl bg-[#211D19] px-4 py-3 text-[12px] text-white">Un truc chic pour vendredi soir</div>
                <div className="overflow-hidden rounded-2xl border border-[#E5DED4] bg-white">
                  <div className="flex gap-3 p-3"><img src={outfits[1].image} alt="Tenue chic" className="h-24 w-20 rounded-xl object-cover" /><div><p className="text-[13px] font-semibold">Vendredi il fera 19 °C, voici une tenue chic.</p><p className="mt-2 text-[10px] text-[#8D6842]">Robe midi · Veste légère · Mocassins</p></div></div>
                </div>
              </div>
            )}
            <button onClick={() => setChatSent(true)} className="w-full rounded-2xl border border-[#D9CEC0] bg-white px-4 py-3 text-left text-[12px] text-[#675F57]">un truc chic pour vendredi soir <span className="float-right">→</span></button>
          </div>
        </div>
      )}

      {cameraOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-[#171512] p-5 text-white">
          <div className="mx-auto max-w-xl">
            <div className="mb-5 flex items-center justify-between"><div><p className="text-[10px] uppercase tracking-widest text-[#C9A77B]">Analyse terminée</p><h3 className="font-serif text-[26px]">Autour de cette pièce</h3></div><button onClick={() => setCameraOpen(false)} className="h-10 w-10 rounded-full bg-white/10">×</button></div>
            <div className="relative mb-6 h-64 overflow-hidden rounded-[28px] border border-[#C9A77B]/50">
              <img src="https://images.unsplash.com/photo-1542272604-787c3835535d?w=700&h=700&fit=crop&auto=format" alt="Veste en jean photographiée" className="h-full w-full object-cover" />
              <div className="absolute inset-5 rounded-2xl border border-dashed border-white/70" />
              <span className="absolute bottom-4 left-4 rounded-full bg-[#C9A77B] px-3 py-1.5 text-[11px] font-bold text-[#171512]">Veste en jean détectée</span>
            </div>
            <p className="mb-3 text-[12px] text-white/55">3 tenues créées avec tes vêtements</p>
            <div className="grid grid-cols-3 gap-2">
              {[outfits[0], outfits[1], outfits[2]].map((item) => <img key={item.name} src={item.image} alt={item.name} className="h-48 w-full rounded-2xl object-cover" />)}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
