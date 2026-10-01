import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { outfitsApi } from '../api'
import { SlotPicker } from '../components/outfit/SlotPicker'
import { Button } from '../components/ui/Button'
import { Chips } from '../components/ui/Chips'
import { TextField } from '../components/ui/Field'
import { Sheet } from '../components/ui/Sheet'
import { ErrorState } from '../components/ui/StatusView'
import { useAvatarConfig } from '../features/avatar/useAvatarConfig'
import { garmentUrlsFor } from '../features/outfits/garmentUrls'
import { useWardrobe } from '../hooks/useWardrobe'
import { useOutfitEditor } from '../stores/outfitStore'
import { AvatarViewer } from '../three/AvatarViewer'
import type { ClothingItem, OutfitSlot } from '../types'
import {
  EMPTY_SELECTION,
  SLOTS,
  outfitFieldsFromSelection,
  slotForCategory,
  type SlotField,
  type SlotSelection,
} from '../utils/garments'

function defaultSelection(items: ClothingItem[]): SlotSelection {
  const oldestFirst = [...items].reverse()
  const pick = (slot: OutfitSlot) =>
    oldestFirst.find((i) => i.glb_url && slotForCategory(i.category) === slot)?.id ?? null
  return { ...EMPTY_SELECTION, top: pick('top'), bottom: pick('bottom'), shoes: pick('shoes') }
}

export function AvatarStudioPage() {
  const [params, setParams] = useSearchParams()
  const outfitId = params.get('outfit')
  const avatar = useAvatarConfig()
  const wardrobe = useWardrobe()
  const { selection, outfit, dirty, setSlot, loadOutfit, markSaved, startNew } = useOutfitEditor()

  const [activeSlot, setActiveSlot] = useState<OutfitSlot>('top')
  const [saving, setSaving] = useState(false)
  const [sheetOpen, setSheetOpen] = useState(false)
  const [newName, setNewName] = useState('')
  const [notice, setNotice] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null)

  useEffect(() => {
    if (!outfitId || outfit?.id === outfitId) return
    outfitsApi
      .get(outfitId)
      .then(loadOutfit)
      .catch(() => setNotice({ kind: 'error', text: 'That outfit could not be loaded.' }))
  }, [outfitId, outfit?.id, loadOutfit])

  useEffect(() => {
    const isBlank = Object.values(selection).every((v) => v === null)
    if (!outfitId && !outfit && !dirty && isBlank && wardrobe.items.length > 0) {
      startNew(defaultSelection(wardrobe.items))
    }
  }, [outfitId, outfit, dirty, selection, wardrobe.items, startNew])

  useEffect(() => {
    if (!notice) return
    const timer = window.setTimeout(() => setNotice(null), 2600)
    return () => window.clearTimeout(timer)
  }, [notice])

  const itemsBySlot = useMemo(() => {
    const groups: Record<OutfitSlot, ClothingItem[]> = { top: [], bottom: [], outerwear: [], shoes: [] }
    for (const item of wardrobe.items) {
      const slot = slotForCategory(item.category)
      if (slot) groups[slot].push(item)
    }
    return groups
  }, [wardrobe.items])

  const garments = useMemo(() => garmentUrlsFor(selection, wardrobe.byId), [selection, wardrobe.byId])

  const slotOptions = SLOTS.map(({ slot, label }) => ({ value: slot, label }))

  const saveChanges = async () => {
    if (!outfit) return setSheetOpen(true)
    const fields = outfitFieldsFromSelection(selection)
    const changed: Partial<Record<SlotField, string | null>> = {}
    for (const key of Object.keys(fields) as SlotField[]) {
      if (fields[key] !== outfit[key]) changed[key] = fields[key]
    }
    setSaving(true)
    try {
      markSaved(await outfitsApi.update(outfit.id, changed))
      setNotice({ kind: 'ok', text: 'Outfit updated' })
    } catch (err) {
      setNotice({ kind: 'error', text: err instanceof Error ? err.message : 'Could not save.' })
    } finally {
      setSaving(false)
    }
  }

  const saveAsNew = async (event: FormEvent) => {
    event.preventDefault()
    const name = newName.trim()
    if (!name) return
    setSaving(true)
    try {
      const created = await outfitsApi.create({
        name,
        ...outfitFieldsFromSelection(selection),
        accessory_ids: [],
      })
      markSaved(created)
      setParams({ outfit: created.id }, { replace: true })
      setSheetOpen(false)
      setNewName('')
      setNotice({ kind: 'ok', text: `“${created.name}” saved` })
    } catch (err) {
      setNotice({ kind: 'error', text: err instanceof Error ? err.message : 'Could not save.' })
    } finally {
      setSaving(false)
    }
  }

  const resetToNew = () => {
    setParams({}, { replace: true })
    startNew(selection)
  }

  return (
    <div className="studio">
      <section className="studio__stage">
        <AvatarViewer avatarUrl={avatar.base_model_url} scale={avatar.scale} garments={garments} />
        {notice && (
          <div className={`toast toast--${notice.kind}`} role="status">
            {notice.text}
          </div>
        )}
      </section>

      <section className="studio__panel">
        <div className="studio__header">
          <div>
            <p className="eyebrow">{outfit ? 'Editing outfit' : 'New outfit'}</p>
            <h1 className="studio__title">
              {outfit?.name ?? 'Dress your avatar'}
              {dirty && outfit && <span className="dot" aria-label="Unsaved changes" />}
            </h1>
          </div>
          <div className="studio__actions">
            {outfit && (
              <Button variant="ghost" size="sm" onClick={resetToNew}>
                New
              </Button>
            )}
            <Button
              size="sm"
              loading={saving && !sheetOpen}
              disabled={outfit !== null && !dirty}
              onClick={saveChanges}
            >
              {outfit ? (dirty ? 'Save' : 'Saved') : 'Save outfit'}
            </Button>
          </div>
        </div>

        <Chips label="Outfit slot" options={slotOptions} value={activeSlot} onChange={setActiveSlot} />

        {wardrobe.error ? (
          <ErrorState message={wardrobe.error} onRetry={wardrobe.reload} />
        ) : wardrobe.loading && wardrobe.items.length === 0 ? (
          <div className="slot-picker__skeleton" aria-busy>
            {[0, 1, 2, 3].map((i) => (
              <span key={i} className="skeleton" />
            ))}
          </div>
        ) : (
          <SlotPicker
            slot={activeSlot}
            items={itemsBySlot[activeSlot]}
            selectedId={selection[activeSlot]}
            onSelect={(id) => setSlot(activeSlot, id)}
          />
        )}

        {outfit && (
          <Button variant="secondary" block onClick={() => setSheetOpen(true)}>
            Save as a new outfit
          </Button>
        )}
      </section>

      <Sheet open={sheetOpen} title="Name this outfit" onClose={() => setSheetOpen(false)}>
        <form className="form" onSubmit={saveAsNew}>
          <TextField
            label="Outfit name"
            placeholder="e.g. Friday dinner"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            autoFocus
            required
            maxLength={120}
          />
          <Button type="submit" size="lg" block loading={saving}>
            Save outfit
          </Button>
        </form>
      </Sheet>
    </div>
  )
}
