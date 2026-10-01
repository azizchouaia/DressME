import type { ClothingItem, OutfitSlot } from '../../types'
import type { SlotSelection } from '../../utils/garments'

/** Resolve a slot selection to the GLB URLs the viewer should load. */
export function garmentUrlsFor(
  selection: SlotSelection,
  byId: Map<string, ClothingItem>,
): Partial<Record<OutfitSlot, string | null>> {
  const urls: Partial<Record<OutfitSlot, string | null>> = {}
  for (const [slot, id] of Object.entries(selection) as [OutfitSlot, string | null][]) {
    urls[slot] = id ? (byId.get(id)?.glb_url ?? null) : null
  }
  return urls
}
