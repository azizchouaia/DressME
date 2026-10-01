import { useState, type FormEvent, type ReactNode } from 'react'
import { CLOTHING_CATEGORIES, type ClothingFields } from '../../types'
import { COLOR_OPTIONS } from '../../utils/colors'
import { CATEGORY_LABELS, capitalize } from '../../utils/garments'
import { Button } from '../ui/Button'
import { SelectField, TextField } from '../ui/Field'

interface Props {
  initial: ClothingFields
  /** Fields pre-filled from AI; shown with a "Suggested" hint so users know to check them. */
  suggested?: Partial<Record<keyof ClothingFields, boolean>>
  submitLabel: string
  submitting?: boolean
  onSubmit: (values: ClothingFields) => void
  secondaryAction?: ReactNode
}

const categoryOptions = CLOTHING_CATEGORIES.map((c) => ({ value: c, label: CATEGORY_LABELS[c] }))
const colorOptions = [
  { value: '', label: 'Not set' },
  ...COLOR_OPTIONS.map((c) => ({ value: c, label: capitalize(c) })),
]
const patternOptions = ['', 'plain', 'striped', 'checked', 'graphic', 'floral', 'other'].map(
  (p) => ({ value: p, label: p ? capitalize(p) : 'Not set' }),
)
const sleeveOptions = ['', 'short', 'long', 'sleeveless', 'three-quarter'].map((s) => ({
  value: s,
  label: s ? capitalize(s) : 'Not set',
}))

function nullable(value: string): string | null {
  const trimmed = value.trim()
  return trimmed === '' ? null : trimmed
}

export function ClothingForm({
  initial,
  suggested = {},
  submitLabel,
  submitting,
  onSubmit,
  secondaryAction,
}: Props) {
  const [values, setValues] = useState(initial)
  const set = <K extends keyof ClothingFields>(key: K, value: ClothingFields[K]) =>
    setValues((v) => ({ ...v, [key]: value }))
  const hint = (key: keyof ClothingFields) => (suggested[key] ? 'Suggested by AI — check it' : undefined)

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    onSubmit({ ...values, name: values.name.trim() })
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <TextField
        label="Name"
        value={values.name}
        onChange={(e) => set('name', e.target.value)}
        required
        maxLength={120}
      />
      <div className="form__row">
        <SelectField
          label="Category"
          value={values.category}
          options={categoryOptions}
          hint={hint('category')}
          onChange={(e) => set('category', e.target.value as ClothingFields['category'])}
        />
        <SelectField
          label="Color"
          value={values.color ?? ''}
          options={colorOptions}
          hint={hint('color')}
          onChange={(e) => set('color', nullable(e.target.value))}
        />
      </div>
      <div className="form__row">
        <SelectField
          label="Pattern"
          value={values.pattern ?? ''}
          options={patternOptions}
          hint={hint('pattern')}
          onChange={(e) => set('pattern', nullable(e.target.value))}
        />
        <SelectField
          label="Sleeve"
          value={values.sleeve_type ?? ''}
          options={sleeveOptions}
          hint={hint('sleeve_type')}
          onChange={(e) => set('sleeve_type', nullable(e.target.value))}
        />
      </div>
      <div className="form__row">
        <TextField
          label="Brand"
          value={values.brand ?? ''}
          placeholder="Optional"
          onChange={(e) => set('brand', nullable(e.target.value))}
        />
        <TextField
          label="Size"
          value={values.size ?? ''}
          placeholder="Optional"
          onChange={(e) => set('size', nullable(e.target.value))}
        />
      </div>
      <TextField
        label="Material"
        value={values.material ?? ''}
        placeholder="Optional"
        onChange={(e) => set('material', nullable(e.target.value))}
      />
      <div className="form__actions">
        {secondaryAction}
        <Button type="submit" size="lg" block loading={submitting}>
          {submitLabel}
        </Button>
      </div>
    </form>
  )
}
