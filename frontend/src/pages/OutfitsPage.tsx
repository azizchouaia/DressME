import { outfitsApi } from '../api'
import { OutfitCard } from '../components/outfit/OutfitCard'
import { ButtonLink } from '../components/ui/Button'
import { PlusIcon } from '../components/ui/icons'
import { PageHeader } from '../components/ui/PageHeader'
import { EmptyState, ErrorState } from '../components/ui/StatusView'
import { useResource } from '../hooks/useResource'
import { useWardrobe } from '../hooks/useWardrobe'
import { useOutfitEditor } from '../stores/outfitStore'
import type { Outfit } from '../types'

export function OutfitsPage() {
  const outfits = useResource(() => outfitsApi.list(), [])
  const { byId } = useWardrobe()
  const editor = useOutfitEditor()

  const remove = async (outfit: Outfit) => {
    if (!window.confirm(`Delete “${outfit.name}”?`)) return
    await outfitsApi.remove(outfit.id)
    outfits.setData((list) => list?.filter((o) => o.id !== outfit.id))
    if (editor.outfit?.id === outfit.id) editor.startNew(editor.selection)
  }

  const list = outfits.data ?? []

  return (
    <div className="page">
      <PageHeader
        title="Outfits"
        subtitle={outfits.loading ? 'Loading…' : `${list.length} saved`}
        action={
          <ButtonLink to="/avatar" size="sm">
            <PlusIcon size={18} /> New
          </ButtonLink>
        }
      />
      {outfits.error ? (
        <ErrorState message={outfits.error} onRetry={outfits.reload} />
      ) : outfits.loading && list.length === 0 ? (
        <div className="stack">
          {[0, 1].map((i) => (
            <div key={i} className="skeleton skeleton--row" />
          ))}
        </div>
      ) : list.length === 0 ? (
        <EmptyState
          title="No outfits yet"
          text="Dress your avatar and save the look to find it here."
          action={<ButtonLink to="/avatar">Dress your avatar</ButtonLink>}
        />
      ) : (
        <div className="stack">
          {list.map((outfit) => (
            <OutfitCard key={outfit.id} outfit={outfit} byId={byId} onDelete={remove} />
          ))}
        </div>
      )}
    </div>
  )
}
