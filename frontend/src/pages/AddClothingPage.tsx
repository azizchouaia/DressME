import { useEffect, useRef, useState, type ChangeEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { wardrobeApi } from '../api'
import { Button } from '../components/ui/Button'
import { CameraIcon, ImageIcon, SparkleIcon } from '../components/ui/icons'
import { PageHeader } from '../components/ui/PageHeader'
import { Spinner } from '../components/ui/StatusView'
import { ClothingForm } from '../components/wardrobe/ClothingForm'
import type { ClothingAnalysis, ClothingFields, ClothingItem } from '../types'
import { CATEGORY_LABELS, capitalize } from '../utils/garments'

type Step =
  | { name: 'pick' }
  | { name: 'preview'; file: File; previewUrl: string }
  | { name: 'working'; label: string; previewUrl: string }
  | {
      name: 'review'
      item: ClothingItem
      analysis: ClothingAnalysis | null
      analysisError: string | null
      previewUrl: string
    }

function initialFields(analysis: ClothingAnalysis | null): ClothingFields {
  const color = analysis?.primary_color ?? null
  const category = analysis?.category ?? 'other'
  const noun = category === 'other' ? 'piece' : CATEGORY_LABELS[category].toLowerCase()
  return {
    name: color ? `${capitalize(color)} ${noun}` : 'New piece',
    category,
    subcategory: analysis?.subcategory ?? null,
    color,
    secondary_color: analysis?.secondary_color ?? null,
    pattern: analysis?.pattern ?? null,
    brand: analysis?.brand ?? null,
    size: null,
    material: null,
    sleeve_type: analysis?.sleeve_type ?? null,
  }
}

export function AddClothingPage() {
  const navigate = useNavigate()
  const cameraInput = useRef<HTMLInputElement>(null)
  const libraryInput = useRef<HTMLInputElement>(null)
  const [step, setStep] = useState<Step>({ name: 'pick' })
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const previewUrl = step.name === 'pick' ? null : step.previewUrl
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl)
    }
  }, [previewUrl])

  const onFile = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    if (!file.type.startsWith('image/')) {
      setError('Please choose an image file.')
      return
    }
    setError(null)
    setStep({ name: 'preview', file, previewUrl: URL.createObjectURL(file) })
  }

  const analyze = async (file: File, url: string) => {
    setError(null)
    setStep({ name: 'working', label: 'Uploading photo…', previewUrl: url })
    let item: ClothingItem
    try {
      item = await wardrobeApi.upload(file)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed.')
      setStep({ name: 'preview', file, previewUrl: url })
      return
    }
    setStep({ name: 'working', label: 'Analyzing clothing…', previewUrl: url })
    try {
      const analysis = await wardrobeApi.analyze(item.id)
      setStep({ name: 'review', item, analysis, analysisError: null, previewUrl: url })
    } catch {
      setStep({
        name: 'review',
        item,
        analysis: null,
        analysisError: 'We couldn’t analyze this photo. Fill in the details yourself.',
        previewUrl: url,
      })
    }
  }

  const confirm = async (values: ClothingFields) => {
    if (step.name !== 'review') return
    setSaving(true)
    try {
      await wardrobeApi.update(step.item.id, values)
      navigate('/wardrobe', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save this item.')
      setSaving(false)
    }
  }

  const discard = async () => {
    if (step.name === 'review') await wardrobeApi.remove(step.item.id).catch(() => undefined)
    setStep({ name: 'pick' })
  }

  return (
    <div className="page add-clothing">
      <PageHeader back title="Add clothing" subtitle="One piece per photo works best." />

      <input ref={cameraInput} type="file" accept="image/*" capture="environment" hidden onChange={onFile} />
      <input ref={libraryInput} type="file" accept="image/*" hidden onChange={onFile} />

      {step.name === 'pick' && (
        <div className="picker">
          <button type="button" className="picker__option" onClick={() => cameraInput.current?.click()}>
            <CameraIcon />
            <span className="picker__title">Take a photo</span>
            <span className="picker__text">Lay the item flat on a plain surface</span>
          </button>
          <button type="button" className="picker__option" onClick={() => libraryInput.current?.click()}>
            <ImageIcon />
            <span className="picker__title">Choose from library</span>
            <span className="picker__text">JPG, PNG or HEIC up to 12 MB</span>
          </button>
        </div>
      )}

      {step.name !== 'pick' && (
        <div className="photo-preview">
          <img src={step.previewUrl} alt="Selected clothing" />
          {step.name === 'working' && (
            <div className="photo-preview__overlay">
              <Spinner label={step.label} />
            </div>
          )}
        </div>
      )}

      {error && <p className="form-error">{error}</p>}

      {step.name === 'preview' && (
        <div className="stack">
          <Button size="lg" block onClick={() => analyze(step.file, step.previewUrl)}>
            <SparkleIcon /> Analyze clothing
          </Button>
          <Button variant="ghost" block onClick={() => setStep({ name: 'pick' })}>
            Choose another photo
          </Button>
        </div>
      )}

      {step.name === 'review' && (
        <>
          <section className="card ai-result">
            <div className="card__head">
              <h2 className="section-title">Detected clothing</h2>
              {step.analysis && (
                <span className="badge">{Math.round(step.analysis.confidence * 100)}% sure</span>
              )}
            </div>
            {step.analysisError ? (
              <p className="muted">{step.analysisError}</p>
            ) : (
              <p className="muted small">
                These are suggestions — review and correct anything before saving.
              </p>
            )}
          </section>
          <ClothingForm
            initial={initialFields(step.analysis)}
            suggested={{
              category: Boolean(step.analysis?.category),
              color: Boolean(step.analysis?.primary_color),
              pattern: Boolean(step.analysis?.pattern),
              sleeve_type: Boolean(step.analysis?.sleeve_type),
            }}
            submitLabel="Confirm and add"
            submitting={saving}
            onSubmit={confirm}
            secondaryAction={
              <Button variant="ghost" block onClick={discard}>
                Discard
              </Button>
            }
          />
        </>
      )}
    </div>
  )
}
