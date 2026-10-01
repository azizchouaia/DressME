import { useState } from 'react'
import { Link } from 'react-router-dom'
import { outfitsApi } from '../api'
import { ButtonLink } from '../components/ui/Button'
import { PlusIcon, SparkleIcon } from '../components/ui/icons'
import { ClothingThumb } from '../components/wardrobe/ClothingThumb'
import { useAvatarConfig } from '../features/avatar/useAvatarConfig'
import { garmentUrlsFor } from '../features/outfits/garmentUrls'
import { useResource } from '../hooks/useResource'
import { useWardrobe } from '../hooks/useWardrobe'
import { useAuthStore } from '../stores/authStore'
import { AvatarViewer } from '../three/AvatarViewer'
import { selectionFromOutfit } from '../utils/garments'

function greeting(date = new Date()): string {
  const hour = date.getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

export function HomePage() {
  const [now] = useState(() => new Date())
  const user = useAuthStore((s) => s.user)
  const avatar = useAvatarConfig()
  const wardrobe = useWardrobe()
  const outfits = useResource(() => outfitsApi.list(), [])
  const today = outfits.data?.[0]
  const count = wardrobe.items.length

  return (
    <div className="page home">
      <header className="home__header">
        <p className="eyebrow">
          {now.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}
        </p>
        <h1 className="display display--md">
          {greeting(now)}, {user?.display_name ?? 'there'}
        </h1>
      </header>

      <section className="card today">
        <div className="card__head">
          <h2 className="section-title">Today’s outfit</h2>
          {today && <span className="muted">{today.name}</span>}
        </div>
        <div className="today__stage">
          {outfits.loading || wardrobe.loading ? (
            <div className="skeleton skeleton--stage" />
          ) : today ? (
            <AvatarViewer
              avatarUrl={avatar.base_model_url}
              scale={avatar.scale}
              garments={garmentUrlsFor(selectionFromOutfit(today), wardrobe.byId)}
              interactive={false}
            />
          ) : (
            <div className="today__empty">
              <p>No outfits yet. Dress your avatar to create your first one.</p>
            </div>
          )}
        </div>
        <ButtonLink to={today ? `/avatar?outfit=${today.id}` : '/avatar'} block>
          {today ? 'View outfit' : 'Create an outfit'}
        </ButtonLink>
      </section>

      <section className="card">
        <div className="card__head">
          <h2 className="section-title">Your wardrobe</h2>
          <Link to="/wardrobe" className="link">
            {wardrobe.loading ? '…' : `${count} ${count === 1 ? 'item' : 'items'}`}
          </Link>
        </div>
        {wardrobe.error ? (
          <p className="form-error">{wardrobe.error}</p>
        ) : (
          <div className="mini-rail">
            {wardrobe.items.slice(0, 8).map((item) => (
              <Link key={item.id} to={`/wardrobe/${item.id}`} className="mini-rail__item" aria-label={item.name}>
                <ClothingThumb item={item} />
              </Link>
            ))}
          </div>
        )}
        <ButtonLink to="/wardrobe/add" variant="secondary" block>
          <PlusIcon size={18} /> Add clothing
        </ButtonLink>
      </section>

      <section className="card stylist">
        <div className="stylist__icon">
          <SparkleIcon />
        </div>
        <div>
          <h2 className="section-title">AI Stylist</h2>
          <p className="stylist__prompt">“What should I wear today?”</p>
          <p className="muted small">Outfit suggestions from your own wardrobe are coming soon.</p>
        </div>
      </section>
    </div>
  )
}
