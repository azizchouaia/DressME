import { Link } from 'react-router-dom'
import type { ClothingItem } from '../../types'
import { describeItem } from '../../utils/garments'
import { CubeIcon } from '../ui/icons'
import { ClothingThumb } from './ClothingThumb'

export function ClothingCard({ item }: { item: ClothingItem }) {
  const extras = [item.brand, item.size && `Size ${item.size}`].filter(Boolean).join(' · ')
  return (
    <Link to={`/wardrobe/${item.id}`} className="clothing-card">
      <div className="clothing-card__media">
        <ClothingThumb item={item} />
        {item.glb_url && (
          <span className="badge badge--floating" title="Can be worn on your avatar">
            <CubeIcon /> 3D
          </span>
        )}
      </div>
      <div className="clothing-card__body">
        <p className="clothing-card__name">{item.name}</p>
        <p className="clothing-card__meta">{describeItem(item)}</p>
        {extras && <p className="clothing-card__extra">{extras}</p>}
      </div>
    </Link>
  )
}
