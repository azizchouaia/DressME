import { useState } from "react";

type CardKind = "outfit" | "shop" | "buy" | "wardrobe";
type Message = { id: number; role: "user" | "ai"; text: string; card?: CardKind };

const quickPrompts = [
  "Entretien demain",
  "Chemise en lin à Tunis",
  "Qu’est-ce que je n’ai pas porté ?",
  "Je l’achète ?",
];

const cardData: Record<CardKind, { title: string; subtitle: string; image: string; action: string }> = {
  outfit: { title: "Entretien · Sobre et assuré", subtitle: "Demain 18 °C · Score 94/100", image: "https://images.unsplash.com/photo-1597308784057-ea6c4e17bfa4?w=500&h=400&fit=crop&auto=format", action: "Planifier pour demain" },
  shop: { title: "Lyoum · La Marsa", subtitle: "Chemise lin blanc · 79 TND · Ouvert jusqu’à 19 h", image: "https://images.unsplash.com/photo-1603252109303-2751441dd157?w=500&h=400&fit=crop&auto=format", action: "Voir sur la carte" },
  buy: { title: "Recommandé · 81/100", subtitle: "8 nouvelles tenues · Aucun doublon", image: "https://images.unsplash.com/photo-1551488831-00ddcb6c6bd3?w=500&h=400&fit=crop&auto=format", action: "Voir le verdict" },
  wardrobe: { title: "Veste kaki", subtitle: "Pas portée depuis 74 jours", image: "https://images.unsplash.com/photo-1551232864-3f0890e580d9?w=500&h=400&fit=crop&auto=format", action: "Créer une tenue" },
};

function getReply(text: string): { text: string; card: CardKind } {
  const lower = text.toLowerCase();
  if (lower.includes("tunis") || lower.includes("lin")) return { text: "J’ai trouvé trois options locales sous 80 TND. Voici la plus proche de ton style.", card: "shop" };
  if (lower.includes("achète") || lower.includes("achete") || lower.includes("acheter")) return { text: "Oui, cette pièce complète réellement ton placard et reste dans ton budget habituel.", card: "buy" };
  if (lower.includes("pas porté") || lower.includes("longtemps")) return { text: "Cette veste est ta pièce la plus oubliée. Je peux construire un look autour d’elle.", card: "wardrobe" };
  return { text: "Demain il fera 18 °C. J’ai préparé une tenue sobre avec uniquement tes vêtements.", card: "outfit" };
}

export default function AssistantScreen() {
  const [messages, setMessages] = useState<Message[]>([
    { id: 0, role: "ai", text: "Bonjour Camille. Je connais ta garde-robe, ton style et la météo. Que veux-tu préparer ?" },
  ]);
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const [memoryOpen, setMemoryOpen] = useState(false);

  const send = (text: string) => {
    if (!text.trim() || typing) return;
    setMessages((current) => [...current, { id: Date.now(), role: "user", text }]);
    setInput("");
    setTyping(true);
    window.setTimeout(() => {
      const reply = getReply(text);
      setMessages((current) => [...current, { id: Date.now() + 1, role: "ai", ...reply }]);
      setTyping(false);
    }, 700);
  };

  return (
    <div className="flex h-[calc(100vh-112px)] flex-col bg-[#F6F3EE]">
      <header className="bg-[#211D19] px-5 pb-5 pt-5 text-white">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3"><div className="flex h-11 w-11 items-center justify-center rounded-full bg-[#C9A77B] font-serif text-xl text-[#211D19]">D</div><div><h1 className="text-[14px] font-semibold">Styliste DressMe</h1><p className="text-[10px] text-white/45">Français · العربية · Darija · English</p></div></div>
          <button onClick={() => setMemoryOpen(true)} className="rounded-full border border-white/15 px-3 py-2 text-[9px] text-white/65">Mémoire</button>
        </div>
      </header>

      <main className="flex-1 space-y-4 overflow-y-auto px-4 py-5 no-scrollbar">
        <div className="mx-auto rounded-full bg-[#EAE3D9] px-3 py-1.5 text-[9px] text-[#81776D] w-fit">Les réponses utilisent ton placard réel</div>
        {messages.map((message) => (
          <div key={message.id} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[84%] ${message.role === "user" ? "items-end" : "items-start"} flex flex-col gap-2`}>
              <div className={`rounded-2xl px-4 py-3 text-[12px] leading-relaxed ${message.role === "user" ? "rounded-br-sm bg-[#211D19] text-white" : "rounded-bl-sm border border-[#E5DED4] bg-white text-[#39332E]"}`}>{message.text}</div>
              {message.card && (
                <article className="w-full overflow-hidden rounded-2xl border border-[#E5DED4] bg-white shadow-sm">
                  <img src={cardData[message.card].image} alt={cardData[message.card].title} className="h-36 w-full object-cover" />
                  <div className="p-3"><p className="text-[12px] font-semibold">{cardData[message.card].title}</p><p className="mt-1 text-[10px] text-[#81776D]">{cardData[message.card].subtitle}</p><p className="mt-2 text-[9px] text-[#9A744B]">Parce que : couleurs assorties, météo, ton style casual.</p><button className="mt-3 w-full rounded-xl bg-[#211D19] py-2.5 text-[10px] font-semibold text-white">{cardData[message.card].action}</button></div>
                </article>
              )}
            </div>
          </div>
        ))}
        {typing && <div className="w-fit rounded-2xl rounded-bl-sm border border-[#E5DED4] bg-white px-4 py-3 text-[11px] text-[#9A744B]">DressMe réfléchit · · ·</div>}
      </main>

      <div className="px-4 pb-2"><div className="flex gap-2 overflow-x-auto no-scrollbar">{quickPrompts.map((prompt) => <button key={prompt} onClick={() => send(prompt)} className="shrink-0 rounded-full border border-[#DED5C9] bg-white px-3 py-2 text-[10px] text-[#6F665D]">{prompt}</button>)}</div></div>
      <div className="border-t border-[#E5DED4] bg-[#F6F3EE] p-4">
        <div className="flex items-center gap-2 rounded-2xl border border-[#DED5C9] bg-white p-2 shadow-sm">
          <button aria-label="Ajouter une photo" className="h-9 w-9 rounded-full bg-[#F0E8DD] text-[#8D6842]">+</button>
          <button aria-label="Dicter une demande" className="h-9 w-9 rounded-full bg-[#F0E8DD] text-[10px] font-bold text-[#8D6842]">MIC</button>
          <input value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => event.key === "Enter" && send(input)} placeholder="Demande une tenue, une boutique…" className="min-w-0 flex-1 bg-transparent px-1 text-[11px] outline-none" />
          <button onClick={() => send(input)} className="h-9 rounded-xl bg-[#211D19] px-4 text-[10px] font-semibold text-white">Envoyer</button>
        </div>
      </div>

      {memoryOpen && (
        <div className="fixed inset-0 z-50 flex items-end bg-black/40" onClick={() => setMemoryOpen(false)}>
          <div className="mx-auto w-full max-w-xl rounded-t-[28px] bg-white p-5" onClick={(event) => event.stopPropagation()}>
            <div className="flex justify-between"><div><p className="text-[10px] font-bold uppercase tracking-wider text-[#9A744B]">Mémoire modifiable</p><h2 className="font-serif text-[24px]">Ce que DressMe retient</h2></div><button onClick={() => setMemoryOpen(false)} className="h-9 w-9 rounded-full bg-[#F6F3EE]">×</button></div>
            <div className="mt-4 space-y-2">{["Tu n’aimes pas le jaune", "Tu préfères les baskets aux mocassins", "Budget habituel : 40–90 TND", "Style visé : plus élégant"].map((memory) => <div key={memory} className="flex items-center justify-between rounded-xl bg-[#F6F3EE] p-3 text-[11px]"><span>{memory}</span><button className="text-[#9A744B]">Modifier</button></div>)}</div>
          </div>
        </div>
      )}
    </div>
  );
}
