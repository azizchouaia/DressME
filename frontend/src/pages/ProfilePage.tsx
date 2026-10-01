import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { bodyApi } from '../api'
import { Button } from '../components/ui/Button'
import { Chips } from '../components/ui/Chips'
import { TextField } from '../components/ui/Field'
import { PageHeader } from '../components/ui/PageHeader'
import { ErrorState, Spinner } from '../components/ui/StatusView'
import { useResource } from '../hooks/useResource'
import { useAuthStore } from '../stores/authStore'
import { useOutfitEditor } from '../stores/outfitStore'
import type { AvatarPreset, BodyMeasurements, BodyProfile } from '../types'

const MEASUREMENTS: { key: keyof BodyMeasurements; label: string; unit: string }[] = [
  { key: 'height_cm', label: 'Height', unit: 'cm' },
  { key: 'weight_kg', label: 'Weight', unit: 'kg' },
  { key: 'chest_cm', label: 'Chest', unit: 'cm' },
  { key: 'waist_cm', label: 'Waist', unit: 'cm' },
  { key: 'hips_cm', label: 'Hips', unit: 'cm' },
  { key: 'shoulder_width_cm', label: 'Shoulders', unit: 'cm' },
  { key: 'arm_length_cm', label: 'Arm length', unit: 'cm' },
  { key: 'leg_length_cm', label: 'Leg length', unit: 'cm' },
]

const PRESETS: { value: AvatarPreset; label: string }[] = [
  { value: 'slim', label: 'Slim' },
  { value: 'average', label: 'Average' },
  { value: 'broad', label: 'Broad' },
]

function BodyProfileForm({
  initial,
  onSaved,
}: {
  initial: BodyProfile
  onSaved: (profile: BodyProfile) => void
}) {
  const [draft, setDraft] = useState(initial)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  const save = async (event: FormEvent) => {
    event.preventDefault()
    setSaving(true)
    setMessage(null)
    try {
      const { source: _source, ...body } = draft
      onSaved(await bodyApi.update(body))
      setMessage('Saved. Your avatar now uses these settings.')
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Could not save.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="form" onSubmit={save}>
      <div className="field">
        <span className="field__label">Avatar build</span>
        <Chips
          label="Avatar build"
          options={PRESETS}
          value={draft.avatar_preset}
          onChange={(avatar_preset) => setDraft({ ...draft, avatar_preset })}
        />
      </div>
      <div className="measure-grid">
        {MEASUREMENTS.map(({ key, label, unit }) => (
          <TextField
            key={key}
            label={`${label} (${unit})`}
            type="number"
            inputMode="decimal"
            step="0.5"
            value={draft[key] ?? ''}
            onChange={(e) =>
              setDraft({ ...draft, [key]: e.target.value === '' ? null : Number(e.target.value) })
            }
          />
        ))}
      </div>
      <Button type="submit" block loading={saving}>
        Save body profile
      </Button>
      {message && <p className="muted center small">{message}</p>}
    </form>
  )
}

export function ProfilePage() {
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()
  const resetEditor = useOutfitEditor((s) => s.startNew)
  const profile = useResource(() => bodyApi.get(), [])

  const signOut = () => {
    logout()
    resetEditor()
    navigate('/welcome', { replace: true })
  }

  return (
    <div className="page">
      <PageHeader title={user?.display_name ?? 'Profile'} subtitle={user?.email} />

      <section className="card">
        <h2 className="section-title">Body profile</h2>
        <p className="muted small">
          All measurements are optional. They shape your avatar — nothing is estimated without
          your confirmation.
        </p>
        {profile.error ? (
          <ErrorState message={profile.error} onRetry={profile.reload} />
        ) : !profile.data ? (
          <Spinner />
        ) : (
          <BodyProfileForm initial={profile.data} onSaved={(p) => profile.setData(() => p)} />
        )}
      </section>

      <Button variant="secondary" block onClick={signOut}>
        Sign out
      </Button>
    </div>
  )
}
