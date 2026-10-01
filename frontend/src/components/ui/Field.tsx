import { useId, type InputHTMLAttributes, type SelectHTMLAttributes } from 'react'

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  hint?: string
}

export function TextField({ label, hint, className, ...rest }: TextFieldProps) {
  const id = useId()
  return (
    <label className={`field ${className ?? ''}`} htmlFor={id}>
      <span className="field__label">{label}</span>
      <input id={id} className="field__control" {...rest} />
      {hint && <span className="field__hint">{hint}</span>}
    </label>
  )
}

interface SelectFieldProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string
  options: { value: string; label: string }[]
  hint?: string
}

export function SelectField({ label, options, hint, className, ...rest }: SelectFieldProps) {
  const id = useId()
  return (
    <label className={`field ${className ?? ''}`} htmlFor={id}>
      <span className="field__label">{label}</span>
      <select id={id} className="field__control" {...rest}>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {hint && <span className="field__hint">{hint}</span>}
    </label>
  )
}
