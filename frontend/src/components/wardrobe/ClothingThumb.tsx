import type { ClothingItem } from '../../types'
import { GarmentIllustration } from './GarmentIllustration'

export function ClothingThumb({
  item,
}: {
  item: Pick<ClothingItem, 'thumbnail_url' | 'image_url' | 'name' | 'category' | 'color'>
}) {
  const src = item.thumbnail_url ?? item.image_url
  return (
    <div className="clothing-thumb">
      {src ? (
        <img src={src} alt={item.name} loading="lazy" />
      ) : (
        <GarmentIllustration category={item.category} color={item.color} />
      )}
    </div>
  )
}
