import { NavLink, Outlet } from 'react-router-dom'
import { AvatarIcon, HangerIcon, HomeIcon, LayersIcon, UserIcon } from '../ui/icons'

const NAV_ITEMS = [
  { to: '/home', label: 'Home', icon: HomeIcon },
  { to: '/wardrobe', label: 'Wardrobe', icon: HangerIcon },
  { to: '/outfits', label: 'Outfits', icon: LayersIcon },
  { to: '/avatar', label: 'Avatar', icon: AvatarIcon },
  { to: '/profile', label: 'Profile', icon: UserIcon },
]

export function AppShell() {
  return (
    <div className="app-shell">
      <main className="app-shell__main">
        <Outlet />
      </main>
      <nav className="bottom-nav" aria-label="Main">
        {NAV_ITEMS.map(({ to, label, icon: IconComponent }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => `bottom-nav__item ${isActive ? 'is-active' : ''}`}
          >
            <IconComponent />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
