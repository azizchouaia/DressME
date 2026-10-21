import { useState } from "react";

type SlotKey = "Haut" | "Bas" | "Chaussures" | "Veste" | "Accessoire";
type Piece = { name: string; slot: SlotKey; image: string };

const pieces: Piece[] = [
  { name: "Chemise blanche", slot: "Haut", image: "https://images.unsplash.com/photo-1556630184-066f7ac4e15f?w=400&h=400&fit=crop&auto=format" },
  { name: "Baskets blanches", slot: "Chaussures", image: "https://images.unsplash.com/photo-1549298916-b41d501d3772?w=400&h=400&fit=crop&auto=format" },
  { name: "Jean marine", slot: "Bas", image: "https://images.unsplash.com/photo-1542272604-787c3835535d?w=400&h=400&fit=crop&auto=format" },
  { name: "Sac camel", slot: "Accessoire", image: "https://images.unsplash.com/photo-1559563458-527698bf5295?w=400&h=400&fit=crop&auto=format" },
  { name: "Blazer sable", slot: "Veste", image: "https://images.unsplash.com/photo-1551232864-3f0890e580d9?w=400&h=400&fit=crop&auto=format" },
];

export default function RecommendationsScreen() {
  const [slots, setSlots] = useState<Partial<Record<SlotKey, Piece>>>({
    Haut: pieces[0],
    Chaussures: pieces[1],
  });
  const [generating, setGenerating] = useState(false);
  const [completed, setCompleted] = useState(false);
  const [view, setView] = useState<"board" | "avatar">("board");
  const [liked, setLiked] = useState(false);
  const slotNames: SlotKey[] = ["Haut", "Bas", "Chaussures", "Veste", "Accessoire"];

  const dropPiece = (piece: Piece) => {
    setSlots((current) => ({ ...current, [piece.slot]: piece }));
    setCompleted(false);
  };

  const complete = () => {
    setGenerating(true);
    window.setTimeout(() => {
      setSlots((current) => ({ ...current, Bas: pieces[2], Accessoire: pieces[3] }));
      setGenerating(false);
      setCompleted(true);
    }, 900);
  };

  return (
    <div className="min-h-full bg-[#171512] pb-8 text-white">
      <section className="px-5 pb-6 pt-7">
        <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[#C9A77B]">Compose · L’IA complète</p>
        <div className="flex items-end justify-between"><h1 className="mt-1 font-serif text-[36px]">Studio</h1><div className="flex rounded-full bg-white/10 p-1">{(["board", "avatar"] as const).map((item) => <button key={item} onClick={() => setView(item)} className={`rounded-full px-3 py-1.5 text-[9px] font-semibold ${view === item ? "bg-[#C9A77B] text-[#211D19]" : "text-white/50"}`}>{item === "board" ? "À plat" : "Avatar"}</button>)}</div></div>
        <p className="mt-2 max-w-sm text-[12px] leading-relaxed text-white/50">Glisse tes pièces dans le board. DressMe trouve ce qui manque sans sortir de ta garde-robe.</p>
      </section>

      <main className="px-4">
        {view === "board" ? <section className="rounded-[28px] bg-[#F6F3EE] p-4 text-[#211D19]">
          <div className="mb-4 flex items-center justify-between">
            <div><p className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#9A744B]">Board du jour</p><h2 className="font-serif text-[23px]">Casual universitaire</h2></div>
            {completed && <div className="rounded-full bg-[#C9A77B] px-3 py-2 text-center"><b className="block text-[15px]">86/100</b><span className="text-[8px] uppercase">compatible</span></div>}
          </div>

          <div className="grid grid-cols-2 gap-3">
            {slotNames.map((slot, index) => {
              const piece = slots[slot];
              return (
                <div
                  key={slot}
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={(event) => {
                    const found = pieces.find((item) => item.name === event.dataTransfer.getData("text/plain"));
                    if (found && found.slot === slot) dropPiece(found);
                  }}
                  className={`relative flex min-h-36 flex-col overflow-hidden rounded-2xl border ${piece ? "border-[#D9CEC0] bg-white" : "empty-slot border-dashed border-[#C9A77B] bg-[#EDE6DC]"} ${index === 4 ? "col-span-2 min-h-28" : ""}`}
                >
                  {piece ? (
                    <><img src={piece.image} alt={piece.name} className="h-28 w-full object-cover" /><div className="p-2.5"><p className="text-[9px] uppercase tracking-wider text-[#9A744B]">{slot}</p><p className="text-[11px] font-semibold">{piece.name}</p></div>{completed && (slot === "Bas" || slot === "Accessoire") && <span className="ai-pop absolute right-2 top-2 rounded-full bg-[#211D19] px-2 py-1 text-[8px] font-bold text-white">CHOIX IA</span>}</>
                  ) : (
                    <div className="flex flex-1 flex-col items-center justify-center"><span className="mb-1 text-xl text-[#B58B5E]">+</span><p className="text-[10px] font-bold uppercase tracking-wider text-[#8C745A]">{slot}</p></div>
                  )}
                </div>
              );
            })}
          </div>

          <button onClick={complete} disabled={generating} className="mt-4 w-full rounded-2xl bg-[#211D19] py-4 text-[13px] font-semibold text-white disabled:opacity-60">
            {generating ? "Je cherche les meilleures associations…" : completed ? "Recalculer avec l’IA" : "Compléter avec l’IA"}
          </button>
        </section> : (
          <section className="rounded-[28px] bg-[#EDE7DF] p-5 text-[#211D19]">
            <div className="flex items-start justify-between"><div><p className="text-[10px] font-bold uppercase tracking-wider text-[#9A744B]">Mannequin personnel</p><h2 className="font-serif text-[23px]">Aperçu sans visage</h2></div><span className="rounded-full bg-white px-3 py-1.5 text-[9px]">86/100</span></div>
            <div className="relative mx-auto my-4 h-80 w-52">
              <div className="absolute left-1/2 top-2 h-14 w-12 -translate-x-1/2 rounded-[45%] bg-[#B98B6F]" />
              <div className="absolute left-1/2 top-16 h-28 w-28 -translate-x-1/2 rounded-t-[44px] bg-[#EEE9E0]" />
              <div className="absolute left-[38px] top-20 h-32 w-6 rotate-6 rounded-full bg-[#B98B6F]" />
              <div className="absolute right-[38px] top-20 h-32 w-6 -rotate-6 rounded-full bg-[#B98B6F]" />
              <div className="absolute left-1/2 top-[174px] h-28 w-24 -translate-x-1/2 rounded-b-2xl bg-[#28313A]" />
              <div className="absolute bottom-0 left-[62px] h-28 w-7 rounded-b-full bg-[#28313A]" />
              <div className="absolute bottom-0 right-[62px] h-28 w-7 rounded-b-full bg-[#28313A]" />
              <span className="absolute left-0 top-28 rounded-full bg-[#C9A77B] px-2 py-1 text-[8px] font-bold">Couleurs assorties</span>
              <span className="absolute right-0 top-52 rounded-full bg-white px-2 py-1 text-[8px] font-bold">Coupe équilibrée</span>
            </div>
            <div className="grid grid-cols-3 gap-2"><button className="rounded-xl bg-white py-3 text-[10px] font-semibold">Pivoter</button><button onClick={() => setLiked(!liked)} className={`rounded-xl py-3 text-[10px] font-semibold ${liked ? "bg-[#C9A77B]" : "bg-white"}`}>{liked ? "Noté" : "J’aime"}</button><button className="rounded-xl bg-[#211D19] py-3 text-[10px] font-semibold text-white">Partager</button></div>
            <p className="mt-3 text-center text-[9px] text-[#81776D]">Taille, carrure et teint ajustables dans ton profil</p>
          </section>
        )}

        <section className="mt-7">
          <div className="mb-3 flex items-end justify-between"><div><p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#C9A77B]">Ton portant</p><h2 className="font-serif text-[23px]">Pièces disponibles</h2></div><span className="text-[10px] text-white/40">Glisser ou toucher</span></div>
          <div className="flex gap-3 overflow-x-auto pb-4 no-scrollbar">
            {pieces.map((piece) => (
              <button
                key={piece.name}
                draggable
                onDragStart={(event) => event.dataTransfer.setData("text/plain", piece.name)}
                onClick={() => dropPiece(piece)}
                className="w-[125px] shrink-0 overflow-hidden rounded-2xl border border-white/10 bg-white/5 text-left"
              >
                <img src={piece.image} alt={piece.name} className="h-32 w-full object-cover" />
                <div className="p-3"><p className="text-[10px] text-[#C9A77B]">{piece.slot}</p><p className="text-[11px] font-semibold text-white">{piece.name}</p></div>
              </button>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
