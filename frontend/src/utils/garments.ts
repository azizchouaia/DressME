import type { ClothingCategory, ClothingItem, Outfit, OutfitSlot } from '../types'

export const CATEGORY_LABELS: Record<ClothingCategory, string> = {
  't-shirt': 'T-Shirt',
  shirt: 'Shirt',
  pants: 'Pants',
  jeans: 'Jeans',
  jacket: 'Jacket',
  dress: 'Dress',
  shoes: 'Shoes',
  accessory: 'Accessory',
  other: 'Other',
}

export const CATEGORY_FILTERS: { value: ClothingCategory | 'all'; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 't-shirt', label: 'T-Shirts' },
  { value: 'shirt', label: 'Shirts' },
  { value: 'pants', label: 'Pants' },
  { value: 'jeans', label: 'Jeans' },
  { value: 'jacket', label: 'Jackets' },
  { value: 'dress', label: 'Dresses' },
  { value: 'shoes', label: 'Shoes' },
  { value: 'accessory', label: 'Accessories' },
  { value: 'other', label: 'Other' },
]

export const SLOTS: { slot: OutfitSlot; label: string; field: SlotField }[] = [
  { slot: 'top', label: 'Top', field: 'shirt_id' },
  { slot: 'bottom', label: 'Bottom', field: 'pants_id' },
  { slot: 'outerwear', label: 'Outerwear', field: 'jacket_id' },
  { slot: 'shoes', label: 'Shoes', field: 'shoes_id' },
]

export type SlotField = 'shirt_id' | 'pants_id' | 'jacket_id' | 'shoes_id'

const CATEGORY_SLOT: Partial<Record<ClothingCategory, OutfitSlot>> = {
  't-shirt': 'top',
  shirt: 'top',
  dress: 'top',
  pants: 'bottom',
  jeans: 'bottom',
  jacket: 'outerwear',
  shoes: 'shoes',
}

export function slotForCategory(category: ClothingCategory): OutfitSlot | null {
  return CATEGORY_SLOT[category] ?? null
}

export type SlotSelection = Record<OutfitSlot, string | null>

export const EMPTY_SELECTION: SlotSelection = {
  top: null,
  bottom: null,
  outerwear: null,
  shoes: null,
}

export function selectionFromOutfit(outfit: Outfit): SlotSelection {
  return {
    top: outfit.shirt_id,
    bottom: outfit.pants_id,
    outerwear: outfit.jacket_id,
    shoes: outfit.shoes_id,
  }
}

export function outfitFieldsFromSelection(selection: SlotSelection): Record<SlotField, string | null> {
  return {
    shirt_id: selection.top,
    pants_id: selection.bottom,
    jacket_id: selection.outerwear,
    shoes_id: selection.shoes,
  }
}

export function describeItem(item: Pick<ClothingItem, 'category' | 'color'>): string {
  const parts = [CATEGORY_LABELS[item.category]]
  if (item.color) parts.push(capitalize(item.color))
  return parts.join(' · ')
}

export function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1)
}
