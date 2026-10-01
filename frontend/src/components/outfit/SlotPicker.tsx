import type { ClothingItem, OutfitSlot } from '../../types'
import { ClothingThumb } from '../wardrobe/ClothingThumb'

interface Props {
  slot: OutfitSlot
  items: ClothingItem[]
  selectedId: string | null
  onSelect: (itemId: string | null) => void
}

/** Horizontal, thumb-friendly list of wardrobe items that fit one avatar slot. */
export function SlotPicker({ slot, items, selectedId, onSelect }: Props) {
  const wearable = items.filter((item) => item.glb_url)
  const without3d = items.length - wearable.length

  return (
    <div className="slot-picker">
      <div className="slot-picker__rail" role="listbox" aria-label={`Choose ${slot}`}>
        <button
          type="button"
          role="option"
          aria-selected={selectedId === null}
          className={`slot-option slot-option--none ${selectedId === null ? 'is-selected' : ''}`}
          onClick={() => onSelect(null)}
        >
          <span className="slot-option__none-icon" aria-hidden>
            ∅
          </span>
          <span className="slot-option__label">None</span>
        </button>
        {wearable.map((item) => (
          <button
            key={item.id}
            type="button"
            role="option"
            aria-selected={selectedId === item.id}
            className={`slot-option ${selectedId === item.id ? 'is-selected' : ''}`}
            onClick={() => onSelect(item.id)}
          >
            <ClothingThumb item={item} />
            <span className="slot-option__label">{item.name}</span>
          </button>
        ))}
      </div>
      {wearable.length === 0 && (
        <p className="slot-picker__note">No 3D-ready items for this slot yet.</p>
      )}
      {without3d > 0 && (
        <p className="slot-picker__note">
          {without3d} {without3d === 1 ? 'item is' : 'items are'} waiting for a 3D model.
        </p>
      )}
    </div>
  )
}
