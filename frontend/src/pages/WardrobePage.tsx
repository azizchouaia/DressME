import { useMemo, useState } from 'react'
import { ButtonLink } from '../components/ui/Button'
import { Chips } from '../components/ui/Chips'
import { PlusIcon } from '../components/ui/icons'
import { PageHeader } from '../components/ui/PageHeader'
import { EmptyState, ErrorState } from '../components/ui/StatusView'
import { ClothingCard } from '../components/wardrobe/ClothingCard'
import { useWardrobe } from '../hooks/useWardrobe'
import type { ClothingCategory } from '../types'
import { CATEGORY_FILTERS } from '../utils/garments'

type Filter = ClothingCategory | 'all'

export function WardrobePage() {
  const { items, loading, error, reload } = useWardrobe()
  const [filter, setFilter] = useState<Filter>('all')

  const counts = useMemo(() => {
    const map = new Map<Filter, number>([['all', items.length]])
    for (const item of items) map.set(item.category, (map.get(item.category) ?? 0) + 1)
    return map
  }, [items])

  const options = CATEGORY_FILTERS.filter((f) => f.value === 'all' || counts.has(f.value)).map(
    (f) => ({ ...f, count: counts.get(f.value) ?? 0 }),
  )
  const visible = filter === 'all' ? items : items.filter((i) => i.category === filter)

  return (
    <div className="page">
      <PageHeader
        title="Wardrobe"
        subtitle={loading ? 'Loading…' : `${items.length} pieces`}
        action={
          <ButtonLink to="/wardrobe/add" size="sm">
            <PlusIcon size={18} /> Add
          </ButtonLink>
        }
      />
      {items.length > 0 && (
        <Chips label="Filter by category" options={options} value={filter} onChange={setFilter} />
      )}

      {error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : loading && items.length === 0 ? (
        <div className="grid">
          {Array.from({ length: 6 }, (_, i) => (
            <div key={i} className="skeleton skeleton--card" />
          ))}
        </div>
      ) : visible.length === 0 ? (
        <EmptyState
          title={items.length === 0 ? 'Your wardrobe is empty' : 'Nothing in this category'}
          text="Snap a photo of something you own to add it."
          action={<ButtonLink to="/wardrobe/add">Add clothing</ButtonLink>}
        />
      ) : (
        <div className="grid">
          {visible.map((item) => (
            <ClothingCard key={item.id} item={item} />
          ))}
        </div>
      )}
    </div>
  )
}
