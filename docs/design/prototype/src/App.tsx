import { useState } from "react";
import HomeScreen from "./screens/HomeScreen";
import WardrobeScreen from "./screens/WardrobeScreen";
import RecommendationsScreen from "./screens/RecommendationsScreen";
import AssistantScreen from "./screens/AssistantScreen";
import ProfileScreen from "./screens/ProfileScreen";
import BottomNav from "./components/BottomNav";

type Tab = "home" | "wardrobe" | "recommendations" | "assistant" | "profile";

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>("home");

  const screens: Record<Tab, React.ReactNode> = {
    home: <HomeScreen onTabChange={setActiveTab} />,
    wardrobe: <WardrobeScreen />,
    recommendations: <RecommendationsScreen />,
    assistant: <AssistantScreen />,
    profile: <ProfileScreen />,
  };

  return (
    <div className="flex flex-col min-h-screen bg-[#FAF9F7]">
      {/* App header bar */}
      <div className="flex items-center justify-between px-6 py-3 bg-white border-b border-[#E5E1DA] sticky top-0 z-40">
        <span className="font-serif text-[22px] italic text-[#1A1714]">DressMe</span>
        <div className="flex items-center gap-3">
          <span className="text-[12px] text-[#7A7470] font-light hidden sm:block">Assistant mode IA</span>
          <div className="w-8 h-8 rounded-full overflow-hidden border-2 border-[#C4A882]">
            <img
              src="https://images.unsplash.com/photo-1636153279424-cb5d1e00f5a2?w=64&h=64&fit=crop&auto=format"
              alt="Profil"
              className="w-full h-full object-cover"
            />
          </div>
        </div>
      </div>

      {/* Screen content */}
      <div className="flex-1 overflow-y-auto no-scrollbar">
        {screens[activeTab]}
      </div>

      {/* Bottom nav */}
      <BottomNav active={activeTab} onChange={setActiveTab} />
    </div>
  );
}
