import { useMemo } from 'react'
import { wardrobeApi } from '../api'
import type { ClothingItem } from '../types'
import { useResource } from './useResource'

export function useWardrobe() {
  const resource = useResource(() => wardrobeApi.list(), [])
  const byId = useMemo(() => {
    const map = new Map<string, ClothingItem>()
    for (const item of resource.data ?? []) map.set(item.id, item)
    return map
  }, [resource.data])
  return { ...resource, items: resource.data ?? [], byId }
}
