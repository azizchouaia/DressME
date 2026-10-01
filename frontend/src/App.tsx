import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { RedirectIfAuthed, RequireAuth } from './features/auth/RequireAuth'
import { AddClothingPage } from './pages/AddClothingPage'
import { AuthPage } from './pages/AuthPage'
import { AvatarStudioPage } from './pages/AvatarStudioPage'
import { ClothingDetailPage } from './pages/ClothingDetailPage'
import { HomePage } from './pages/HomePage'
import { OutfitsPage } from './pages/OutfitsPage'
import { ProfilePage } from './pages/ProfilePage'
import { WardrobePage } from './pages/WardrobePage'
import { WelcomePage } from './pages/WelcomePage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/welcome" element={<RedirectIfAuthed><WelcomePage /></RedirectIfAuthed>} />
        <Route path="/login" element={<RedirectIfAuthed><AuthPage mode="login" /></RedirectIfAuthed>} />
        <Route path="/register" element={<RedirectIfAuthed><AuthPage mode="register" /></RedirectIfAuthed>} />

        <Route element={<RequireAuth><AppShell /></RequireAuth>}>
          <Route path="/home" element={<HomePage />} />
          <Route path="/wardrobe" element={<WardrobePage />} />
          <Route path="/wardrobe/add" element={<AddClothingPage />} />
          <Route path="/wardrobe/:id" element={<ClothingDetailPage />} />
          <Route path="/outfits" element={<OutfitsPage />} />
          <Route path="/avatar" element={<AvatarStudioPage />} />
          <Route path="/profile" element={<ProfilePage />} />
        </Route>

        <Route path="*" element={<Navigate to="/home" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
