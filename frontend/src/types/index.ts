export const CLOTHING_CATEGORIES = [
  't-shirt',
  'shirt',
  'pants',
  'jeans',
  'jacket',
  'dress',
  'shoes',
  'accessory',
  'other',
] as const

export type ClothingCategory = (typeof CLOTHING_CATEGORIES)[number]

export type ClothingStatus =
  | 'uploaded'
  | 'analyzing'
  | 'analyzed'
  | 'processing_3d'
  | 'ready'
  | 'failed'

export type AvatarPreset = 'slim' | 'average' | 'broad'

/** Slots on the avatar. Each maps to one Outfit foreign key. */
export type OutfitSlot = 'top' | 'bottom' | 'outerwear' | 'shoes'

export interface User {
  id: string
  email: string
  display_name: string
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: User
}

export interface ClothingAnalysis {
  category: ClothingCategory | null
  subcategory: string | null
  primary_color: string | null
  secondary_color: string | null
  pattern: string | null
  sleeve_type: string | null
  brand: string | null
  confidence: number
  analyzer: string
}

export interface ClothingFields {
  name: string
  category: ClothingCategory
  subcategory: string | null
  color: string | null
  secondary_color: string | null
  pattern: string | null
  brand: string | null
  size: string | null
  material: string | null
  sleeve_type: string | null
}

export interface ClothingItem extends ClothingFields {
  id: string
  user_id: string
  image_url: string | null
  thumbnail_url: string | null
  glb_url: string | null
  status: ClothingStatus
  ai_analysis: ClothingAnalysis | null
  created_at: string
  updated_at: string
}

export type ClothingUpdate = Partial<ClothingFields> & { glb_url?: string | null }

export interface Outfit {
  id: string
  user_id: string
  name: string
  shirt_id: string | null
  pants_id: string | null
  jacket_id: string | null
  shoes_id: string | null
  accessory_ids: string[]
  created_at: string
  updated_at: string
}

export type OutfitInput = Pick<
  Outfit,
  'name' | 'shirt_id' | 'pants_id' | 'jacket_id' | 'shoes_id' | 'accessory_ids'
>

export interface BodyMeasurements {
  height_cm: number | null
  weight_kg: number | null
  chest_cm: number | null
  waist_cm: number | null
  hips_cm: number | null
  shoulder_width_cm: number | null
  arm_length_cm: number | null
  leg_length_cm: number | null
}

export interface BodyProfile extends BodyMeasurements {
  avatar_preset: AvatarPreset
  source: string
}

export interface AvatarConfig {
  base_model_url: string
  preset: AvatarPreset
  scale: { x: number; y: number; z: number }
  parameters: Record<string, number>
}
