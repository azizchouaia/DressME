import { useState } from "react";

type Section = "style" | "buy" | "local" | "plus";
type BuyStep = "idle" | "loading" | "result";

const localItems = [
  { name: "Trench sable", brand: "Anissa Aida", city: "Tunis", price: 240, match: 94, image: "https://images.unsplash.com/photo-1551488831-00ddcb6c6bd3?w=500&h=620&fit=crop&auto=format" },
  { name: "Chemise en lin", brand: "Lyoum", city: "La Marsa", price: 89, match: 92, image: "https://images.unsplash.com/photo-1603252109303-2751441dd157?w=500&h=620&fit=crop&auto=format" },
  { name: "Sac en cuir", brand: "Kenenti", city: "Tunis", price: 120, match: 89, image: "https://images.unsplash.com/photo-1559563458-527698bf5295?w=500&h=620&fit=crop&auto=format" },
  { name: "Mocassins", brand: "Dorra", city: "Sfax", price: 135, match: 86, image: "https://images.unsplash.com/photo-1543163521-1bf539c55dd2?w=500&h=620&fit=crop&auto=format" },
];

const feed = [
  { name: "Inès", caption: "Lin et tons sable pour Tunis", likes: 42, image: "https://images.unsplash.com/photo-1529399447871-731cff7f696b?w=600&h=700&fit=crop&auto=format" },
  { name: "Sarra", caption: "Mon look local de la semaine", likes: 31, image: "https://images.unsplash.com/photo-1693611282973-f2aace989928?w=600&h=700&fit=crop&auto=format" },
];

function StyleSlider({ left, right, value }: { left: string; right: string; value: number }) {
  return (
    <div>
      <div className="mb-2 flex justify-between text-[11px] font-medium text-[#6F665D]"><span>{left}</span><span>{right}</span></div>
      <div className="relative h-2 rounded-full bg-[#E9E2D9]"><div className="h-full rounded-full bg-[#B88D5D]" style={{ width: `${value}%` }} /><div className="absolute top-1/2 h-4 w-4 -translate-y-1/2 rounded-full border-2 border-white bg-[#211D19] shadow" style={{ left: `calc(${value}% - 8px)` }} /></div>
    </div>
  );
}

function Avatar({ jacket = false }: { jacket?: boolean }) {
  return (
    <div className="relative mx-auto h-64 w-40">
      <div className="absolute left-1/2 top-2 h-12 w-10 -translate-x-1/2 rounded-[45%] bg-[#B98B6F]" />
      <div className={`absolute left-1/2 top-14 h-24 w-24 -translate-x-1/2 rounded-t-[38px] ${jacket ? "bg-[#B28A62]" : "bg-[#E8E0D5]"}`} />
      <div className="absolute left-[30px] top-16 h-28 w-5 rotate-6 rounded-full bg-[#B98B6F]" />
      <div className="absolute right-[30px] top-16 h-28 w-5 -rotate-6 rounded-full bg-[#B98B6F]" />
      <div className="absolute left-1/2 top-[148px] h-24 w-20 -translate-x-1/2 rounded-b-2xl bg-[#28313A]" />
      <div className="absolute bottom-0 left-[48px] h-24 w-6 rounded-b-full bg-[#28313A]" />
      <div className="absolute bottom-0 right-[48px] h-24 w-6 rounded-b-full bg-[#28313A]" />
    </div>
  );
}

export default function ProfileScreen() {
  const [section, setSection] = useState<Section>("style");
  const [buyStep, setBuyStep] = useState<BuyStep>("idle");
  const [showTryOn, setShowTryOn] = useState(false);
  const [city, setCity] = useState("Toutes");
  const [tripReady, setTripReady] = useState(false);
  const [shared, setShared] = useState(false);

  const analyze = () => {
    setBuyStep("loading");
    window.setTimeout(() => setBuyStep("result"), 1000);
  };

  return (
    <div className="min-h-full bg-[#F6F3EE] pb-8">
      <section className="relative overflow-hidden bg-[#211D19] px-5 pb-7 pt-7 text-white">
        <div className="absolute right-0 top-0 h-52 w-52 rounded-full bg-[#A97C50]/20 blur-3xl" />
        <div className="relative flex items-center gap-4">
          <img src="https://images.unsplash.com/photo-1636153279424-cb5d1e00f5a2?w=180&h=180&fit=crop&auto=format" alt="Camille" className="h-16 w-16 rounded-full border-2 border-[#C9A77B] object-cover" />
          <div><p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[#C9A77B]">Ton espace</p><h1 className="font-serif text-[29px]">Camille Martin</h1><p className="text-[11px] text-white/50">Casual minimal · Tunis</p></div>
        </div>
        <div className="relative mt-5 grid grid-cols-3 gap-2">
          {[["64", "pièces"], ["47", "réactions"], ["68", "score durable"]].map(([value, label]) => <div key={label} className="rounded-2xl border border-white/10 bg-white/5 py-3 text-center"><b className="block text-[18px]">{value}</b><span className="text-[9px] text-white/45">{label}</span></div>)}
        </div>
      </section>

      <nav className="sticky top-0 z-20 flex gap-2 overflow-x-auto bg-[#F6F3EE]/95 px-4 py-4 backdrop-blur no-scrollbar">
        {([["style", "Mon style"], ["buy", "Smart Buy"], ["local", "Local"], ["plus", "Plus"]] as [Section, string][]).map(([id, label]) => (
          <button key={id} onClick={() => setSection(id)} className={`shrink-0 rounded-full px-4 py-2 text-[11px] font-semibold ${section === id ? "bg-[#211D19] text-white" : "border border-[#DED5C9] bg-white text-[#71685F]"}`}>{label}</button>
        ))}
      </nav>

      {section === "style" && (
        <main className="space-y-4 px-4">
          <section className="rounded-[24px] border border-[#E5DED4] bg-white p-5">
            <div className="mb-5 flex items-start justify-between"><div><p className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#9A744B]">Profil adaptatif</p><h2 className="font-serif text-[23px]">L’IA apprend ton style</h2></div><span className="rounded-full bg-[#F0E8DD] px-3 py-1.5 text-[9px] text-[#8D6842]">47 réactions</span></div>
            <div className="space-y-6"><StyleSlider left="Formel" right="Décontracté" value={72} /><StyleSlider left="Neutre" right="Coloré" value={34} /><StyleSlider left="Ajusté" right="Oversize" value={58} /></div>
            <button className="mt-6 w-full rounded-xl border border-[#DED5C9] py-3 text-[11px] font-semibold">Corriger mon profil</button>
          </section>

          <section className="rounded-[24px] bg-[#211D19] p-5 text-white">
            <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#C9A77B]">Empreinte vestimentaire</p>
            <div className="mt-4 flex items-center gap-5">
              <div className="relative h-32 w-32 shrink-0 rounded-full border-[18px] border-[#C9A77B]"><div className="absolute inset-1 rounded-full border-[12px] border-[#7E654E]" /><span className="absolute inset-0 flex items-center justify-center text-[11px] font-bold">CASUAL</span></div>
              <div className="space-y-2 text-[11px]"><p><b className="text-[#C9A77B]">45 %</b> casual</p><p><b className="text-[#C9A77B]">30 %</b> minimal</p><p><b className="text-[#C9A77B]">15 %</b> sport</p><p><b className="text-[#C9A77B]">10 %</b> classique</p></div>
            </div>
          </section>

          <section className="rounded-[24px] border border-[#E5DED4] bg-white p-5">
            <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#9A744B]">Insights réels</p><h2 className="font-serif text-[22px]">Ce que tu portes vraiment</h2>
            <div className="my-4 flex gap-2">{["bg-[#171512]", "bg-[#E8E0D5]", "bg-[#C39A72]", "bg-[#33404D]", "bg-[#7A6B58]"].map((color) => <div key={color} className={`h-10 flex-1 rounded-xl ${color}`} />)}</div>
            <div className="grid grid-cols-2 gap-2"><div className="rounded-xl bg-[#F6F3EE] p-3"><span className="text-[9px] text-[#81776D]">Pièce favorite</span><b className="block text-[12px]">Jean bleu droit</b></div><div className="rounded-xl bg-[#F6F3EE] p-3"><span className="text-[9px] text-[#81776D]">Évolution</span><b className="block text-[12px]">Plus minimaliste</b></div></div>
          </section>
        </main>
      )}

      {section === "buy" && (
        <main className="space-y-4 px-4">
          {buyStep !== "result" ? (
            <section className="rounded-[28px] bg-[#211D19] p-5 text-white">
              <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#C9A77B]">Décider en magasin</p><h2 className="mt-1 font-serif text-[27px]">Est-ce que je l’achète ?</h2><p className="mt-2 text-[12px] leading-relaxed text-white/55">Photographie la pièce, ajoute son prix et obtiens un verdict basé sur ton placard.</p>
              <div className="mt-5 h-52 overflow-hidden rounded-2xl border border-dashed border-white/25 bg-white/5">
                <img src="https://images.unsplash.com/photo-1551488831-00ddcb6c6bd3?w=650&h=500&fit=crop&auto=format" alt="Veste candidate" className="h-full w-full object-cover opacity-75" />
              </div>
              <div className="mt-3 flex gap-2"><div className="flex-1 rounded-xl bg-white/10 px-4 py-3 text-[12px]">Veste camel</div><div className="w-28 rounded-xl bg-white/10 px-4 py-3 text-[12px]">120 TND</div></div>
              <button onClick={analyze} disabled={buyStep === "loading"} className="mt-3 w-full rounded-2xl bg-[#C9A77B] py-4 text-[13px] font-bold text-[#211D19]">{buyStep === "loading" ? "Analyse du placard…" : "Analyser cet achat"}</button>
            </section>
          ) : (
            <>
              <section className="rounded-[28px] border border-[#B9D8C5] bg-[#EAF5EE] p-5">
                <div className="flex items-start justify-between"><div><p className="text-[10px] font-bold uppercase tracking-wider text-[#39704D]">Verdict Smart Buy</p><h2 className="font-serif text-[28px] text-[#214C31]">Recommandé</h2><p className="mt-1 text-[11px] text-[#4D6E58]">Un vrai ajout, sans doublon direct.</p></div><div className="flex h-20 w-20 items-center justify-center rounded-full border-8 border-[#4C9366] bg-white text-center"><b className="text-[22px] text-[#214C31]">81</b></div></div>
              </section>
              <section className="rounded-[24px] border border-[#E5DED4] bg-white p-5">
                <p className="mb-4 text-[10px] font-bold uppercase tracking-[0.16em] text-[#9A744B]">Pourquoi ce score</p>
                {[["Doublon", 88], ["Nouvelles tenues", 76], ["Ton style", 92], ["Budget", 70]].map(([label, value]) => <div key={label as string} className="mb-4"><div className="mb-1 flex justify-between text-[11px]"><span>{label}</span><b>{value}%</b></div><div className="h-1.5 rounded-full bg-[#EEE8E0]"><div className="h-full rounded-full bg-[#B78C5B]" style={{ width: `${value}%` }} /></div></div>)}
                <div className="rounded-xl bg-[#F6F3EE] p-3 text-[11px] leading-relaxed text-[#675F57]">Crée 8 nouvelles tenues · proche de ton style · dans ton budget · environ 4 TND par port.</div>
              </section>
              <section className="rounded-[24px] border border-[#E8D1B2] bg-[#FFF6E9] p-4"><p className="text-[10px] font-bold uppercase tracking-wider text-[#9A6733]">Vérification anti-doublon</p><p className="mt-1 text-[12px] text-[#6E5540]">Tu as 1 veste proche, mais sa coupe et sa matière sont différentes.</p></section>
              <div className="grid grid-cols-2 gap-3"><button onClick={() => setShowTryOn(true)} className="rounded-2xl bg-[#211D19] py-4 text-[12px] font-semibold text-white">L’essayer sur l’avatar</button><button onClick={() => setSection("local")} className="rounded-2xl bg-[#C9A77B] py-4 text-[12px] font-semibold">Alternative locale</button></div>
              <button onClick={() => setBuyStep("idle")} className="w-full py-2 text-[11px] text-[#81776D]">Analyser une autre pièce</button>
            </>
          )}
        </main>
      )}

      {section === "local" && (
        <main className="px-4">
          <div className="mb-4"><p className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#9A744B]">Mode tunisienne</p><h2 className="font-serif text-[27px]">Marques qui te ressemblent</h2><p className="mt-1 text-[11px] text-[#81776D]">Prix en dinars, disponibilité locale et affinité style.</p></div>
          <div className="mb-4 flex gap-2 overflow-x-auto no-scrollbar">{["Toutes", "Tunis", "La Marsa", "Sfax"].map((item) => <button key={item} onClick={() => setCity(item)} className={`rounded-full px-4 py-2 text-[10px] font-semibold ${city === item ? "bg-[#211D19] text-white" : "border border-[#DED5C9] bg-white"}`}>{item}</button>)}</div>
          <div className="grid grid-cols-2 gap-3">
            {localItems.filter((item) => city === "Toutes" || item.city === city).map((item) => (
              <article key={item.name} className="overflow-hidden rounded-2xl border border-[#E5DED4] bg-white">
                <div className="relative h-48"><img src={item.image} alt={item.name} className="h-full w-full object-cover" /><span className="absolute right-2 top-2 rounded-full bg-[#211D19]/80 px-2 py-1 text-[9px] font-bold text-white">{item.match}% style</span></div>
                <div className="p-3"><p className="text-[12px] font-semibold">{item.name}</p><p className="text-[10px] text-[#81776D]">{item.brand} · {item.city}</p><div className="mt-2 flex justify-between"><b className="text-[11px]">{item.price} TND</b><button onClick={() => setShowTryOn(true)} className="text-[9px] font-bold text-[#9A744B]">Essayer</button></div><p className="mt-2 border-t border-[#EEE8E0] pt-2 text-[9px] text-[#81776D]">Marque tunisienne · va avec 6 tenues</p></div>
              </article>
            ))}
          </div>
        </main>
      )}

      {section === "plus" && (
        <main className="space-y-4 px-4">
          <section className="rounded-[24px] border border-[#E5DED4] bg-white p-5">
            <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#9A744B]">Planificateur voyage</p><h2 className="font-serif text-[23px]">Djerba · 12–15 juillet</h2><p className="mt-1 text-[11px] text-[#81776D]">Plage + dîner · uniquement tes pièces</p>
            {!tripReady ? <button onClick={() => setTripReady(true)} className="mt-4 w-full rounded-2xl bg-[#211D19] py-3.5 text-[12px] font-semibold text-white">Générer ma valise</button> : <div className="mt-4 grid grid-cols-4 gap-2">{["Ven", "Sam", "Dim", "Lun"].map((day, index) => <div key={day} className="rounded-xl bg-[#F6F3EE] p-2 text-center"><b className="text-[9px]">{day}</b><img src={localItems[index].image} alt={`Tenue ${day}`} className="mt-2 h-20 w-full rounded-lg object-cover" /><span className="mt-1 block text-[8px] text-[#81776D]">Prête</span></div>)}</div>}
          </section>

          <section className="rounded-[24px] bg-[#211D19] p-5 text-white">
            <div className="flex items-end justify-between"><div><p className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#C9A77B]">Communauté</p><h2 className="font-serif text-[23px]">Looks proches du tien</h2></div><button onClick={() => setShared(true)} className="rounded-full bg-[#C9A77B] px-3 py-2 text-[9px] font-bold text-[#211D19]">{shared ? "Partagé" : "Partager mon look"}</button></div>
            <div className="mt-4 flex gap-3 overflow-x-auto no-scrollbar">{feed.map((post) => <article key={post.name} className="w-[180px] shrink-0 overflow-hidden rounded-2xl bg-white/10"><img src={post.image} alt={post.caption} className="h-48 w-full object-cover" /><div className="p-3"><p className="text-[11px] font-semibold">{post.name}</p><p className="mt-1 text-[9px] text-white/50">{post.caption}</p><p className="mt-2 text-[9px] text-[#C9A77B]">{post.likes} j’aime · Enregistrer</p></div></article>)}</div>
          </section>

          <section className="rounded-[24px] border border-[#E5DED4] bg-white p-5">
            <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#9A744B]">Stats mensuelles</p><h2 className="font-serif text-[23px]">Ton mois en un regard</h2>
            <div className="mt-4 grid grid-cols-3 gap-2 text-center">{[["23", "tenues"], ["11", "pièces sauvées"], ["74%", "1er choix accepté"]].map(([value, label]) => <div key={label} className="rounded-xl bg-[#F6F3EE] p-3"><b className="block text-[17px]">{value}</b><span className="text-[8px] text-[#81776D]">{label}</span></div>)}</div>
          </section>
        </main>
      )}

      {showTryOn && (
        <div className="fixed inset-0 z-50 flex items-end bg-black/50" onClick={() => setShowTryOn(false)}>
          <div className="mx-auto w-full max-w-xl rounded-t-[30px] bg-[#EDE7DF] p-5" onClick={(event) => event.stopPropagation()}>
            <div className="flex items-start justify-between"><div><p className="text-[10px] font-bold uppercase tracking-wider text-[#9A744B]">Essayage privé</p><h3 className="font-serif text-[25px]">Sur ton avatar</h3></div><button onClick={() => setShowTryOn(false)} className="h-9 w-9 rounded-full bg-white">×</button></div>
            <Avatar jacket />
            <div className="grid grid-cols-2 gap-3"><button className="rounded-2xl bg-[#211D19] py-3 text-[11px] font-semibold text-white">Faire pivoter</button><button className="rounded-2xl bg-[#C9A77B] py-3 text-[11px] font-semibold">Partager l’essayage</button></div>
            <p className="mt-3 text-center text-[9px] text-[#81776D]">Avatar sans visage · aucune donnée biométrique</p>
          </div>
        </div>
      )}
    </div>
  );
}
