import type { ClothingCategory } from '../../types'
import { isLight, swatchFor } from '../../utils/colors'

const PATHS: Partial<Record<ClothingCategory, string>> & { other: string } = {
  't-shirt': 'M36 14l-18 9 6 14 8-3v40h36V34l8 3 6-14-18-9c-2 6-7 9-14 9s-12-3-14-9z',
  shirt:
    'M36 14l-16 8-6 44 9 2 5-30v38h44V38l5 30 9-2-6-44-16-8c-2 6-7 9-14 9s-12-3-14-9z',
  jacket:
    'M35 13l-15 8-7 46 10 2 5-30v37h20V30l-6-14zM65 13l15 8 7 46-10 2-5-30v37H52V30l6-14z',
  pants: 'M30 14h40l4 70H56l-6-46-6 46H26z',
  jeans: 'M30 14h40l4 70H56l-6-46-6 46H26z',
  dress: 'M38 12h24l-2 16 16 54H24l16-54z',
  shoes: 'M14 58c0-8 4-14 10-16l14 8c6 3 14 4 22 4h10c8 0 14 6 14 12v4H14z',
  accessory: 'M50 22a22 22 0 1 0 0.01 0zM50 34a10 10 0 1 1-0.01 0z',
  other: 'M24 24h52v52H24z',
}

export function GarmentIllustration({
  category,
  color,
}: {
  category: ClothingCategory
  color: string | null
}) {
  const fill = swatchFor(color)
  const stroke = isLight(fill) ? 'rgb(0 0 0 / 0.14)' : 'rgb(255 255 255 / 0.1)'
  return (
    <svg viewBox="0 0 100 100" className="garment-illustration" aria-hidden>
      <path d={PATHS[category] ?? PATHS.other} fill={fill} stroke={stroke} strokeWidth="1.5" strokeLinejoin="round" fillRule="evenodd" />
    </svg>
  )
}
