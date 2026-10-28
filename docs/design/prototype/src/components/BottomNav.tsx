type Tab = "home" | "wardrobe" | "recommendations" | "assistant" | "profile";

interface Props {
  active: Tab;
  onChange: (tab: Tab) => void;
}

const tabs: { id: Tab; label: string; icon: (active: boolean) => React.ReactNode }[] = [
  {
    id: "home",
    label: "Today",
    icon: (a) => (
      <svg width="22" height="22" viewBox="0 0 24 24" fill={a ? "#1A1714" : "none"} stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 9L12 2l9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
        <polyline points="9 22 9 12 15 12 15 22" />
      </svg>
    ),
  },
  {
    id: "wardrobe",
    label: "Garde-robe",
    icon: (a) => (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="3" width="20" height="14" rx="2" fill={a ? "#1A1714" : "none"} />
        <path d="M9 8l-2 2 2 2M15 8l2 2-2 2" stroke={a ? "white" : "currentColor"} />
      </svg>
    ),
  },
  {
    id: "recommendations",
    label: "Studio",
    icon: (a) => (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2L2 7l10 5 10-5-10-5z" fill={a ? "#1A1714" : "none"} />
        <path d="M2 17l10 5 10-5" />
        <path d="M2 12l10 5 10-5" />
      </svg>
    ),
  },
  {
    id: "assistant",
    label: "Assistant",
    icon: (a) => (
      <svg width="22" height="22" viewBox="0 0 24 24" fill={a ? "#1A1714" : "none"} stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
      </svg>
    ),
  },
  {
    id: "profile",
    label: "Profil",
    icon: (a) => (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
        <circle cx="12" cy="7" r="4" fill={a ? "#1A1714" : "none"} />
      </svg>
    ),
  },
];

export default function BottomNav({ active, onChange }: Props) {
  return (
    <div className="sticky bottom-0 bg-white border-t border-[#E5E1DA] flex items-center justify-around px-2 py-2 z-40 shadow-lg">
      {tabs.map((tab) => {
        const isActive = active === tab.id;
        return (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            className="flex flex-col items-center gap-1 flex-1 py-1.5 relative tab-transition"
          >
            {isActive && (
              <span className="absolute -top-2 left-1/2 -translate-x-1/2 w-6 h-1 rounded-full" style={{ background: "linear-gradient(135deg,#C4A882,#8B6345)" }} />
            )}
            <span style={{ color: isActive ? "#1A1714" : "#B0AAA3" }}>
              {tab.icon(isActive)}
            </span>
            <span className="text-[10px] font-semibold" style={{ color: isActive ? "#1A1714" : "#B0AAA3" }}>
              {tab.label}
            </span>
          </button>
        );
      })}
    </div>
  );
}
