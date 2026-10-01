import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { wardrobeApi } from '../api'
import { Button } from '../components/ui/Button'
import { CubeIcon } from '../components/ui/icons'
import { PageHeader } from '../components/ui/PageHeader'
import { ErrorState, Spinner } from '../components/ui/StatusView'
import { ClothingForm } from '../components/wardrobe/ClothingForm'
import { ClothingThumb } from '../components/wardrobe/ClothingThumb'
import { useResource } from '../hooks/useResource'
import type { ClothingFields } from '../types'

export function ClothingDetailPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const { data: item, error, loading, reload, setData } = useResource(() => wardrobeApi.get(id), [id])
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  if (loading && !item) return <Spinner label="Loading item…" />
  if (error || !item) return <ErrorState message={error ?? 'Item not found'} onRetry={reload} />

  const save = async (values: ClothingFields) => {
    setSaving(true)
    setMessage(null)
    try {
      const updated = await wardrobeApi.update(item.id, values)
      setData(() => updated)
      setMessage('Changes saved')
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Could not save.')
    } finally {
      setSaving(false)
    }
  }

  const remove = async () => {
    if (!window.confirm(`Remove “${item.name}” from your wardrobe?`)) return
    setDeleting(true)
    try {
      await wardrobeApi.remove(item.id)
      navigate('/wardrobe', { replace: true })
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Could not delete.')
      setDeleting(false)
    }
  }

  return (
    <div className="page detail">
      <PageHeader back title={item.name} />
      <div className="detail__media">
        <ClothingThumb item={item} />
      </div>
      <p className="detail__status">
        {item.glb_url ? (
          <>
            <CubeIcon size={16} /> Ready to wear on your avatar
          </>
        ) : (
          'No 3D model yet — this piece shows in your wardrobe but not on the avatar.'
        )}
      </p>
      <ClothingForm
        key={item.updated_at}
        initial={item}
        submitLabel="Save changes"
        submitting={saving}
        onSubmit={save}
      />
      {message && <p className="muted center">{message}</p>}
      <Button variant="danger" block loading={deleting} onClick={remove}>
        Delete item
      </Button>
    </div>
  )
}
