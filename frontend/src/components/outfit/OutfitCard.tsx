import { Link } from 'react-router-dom'
import type { ClothingItem, Outfit } from '../../types'
import { SLOTS } from '../../utils/garments'
import { ClothingThumb } from '../wardrobe/ClothingThumb'

interface Props {
  outfit: Outfit
  byId: Map<string, ClothingItem>
  onDelete?: (outfit: Outfit) => void
}

export function OutfitCard({ outfit, byId, onDelete }: Props) {
  const pieces = SLOTS.map(({ field }) => outfit[field])
    .map((id) => (id ? byId.get(id) : undefined))
    .filter((item): item is ClothingItem => item !== undefined)

  return (
    <article className="outfit-card">
      <Link to={`/avatar?outfit=${outfit.id}`} className="outfit-card__link">
        <div className="outfit-card__pieces">
          {pieces.length === 0 && <p className="outfit-card__empty">No items</p>}
          {pieces.map((item) => (
            <ClothingThumb key={item.id} item={item} />
          ))}
        </div>
        <div className="outfit-card__body">
          <p className="outfit-card__name">{outfit.name}</p>
          <p className="outfit-card__meta">{pieces.map((p) => p.name).join(' · ') || 'Empty outfit'}</p>
        </div>
      </Link>
      {onDelete && (
        <button
          type="button"
          className="outfit-card__delete"
          onClick={() => onDelete(outfit)}
          aria-label={`Delete ${outfit.name}`}
        >
          Delete
        </button>
      )}
    </article>
  )
}
