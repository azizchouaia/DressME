interface Props<T extends string> {
  options: { value: T; label: string; count?: number }[]
  value: T
  onChange: (value: T) => void
  label: string
}

export function Chips<T extends string>({ options, value, onChange, label }: Props<T>) {
  return (
    <div className="chips" role="tablist" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="tab"
          aria-selected={option.value === value}
          className={`chip ${option.value === value ? 'is-active' : ''}`}
          onClick={() => onChange(option.value)}
        >
          {option.label}
          {option.count !== undefined && <span className="chip__count">{option.count}</span>}
        </button>
      ))}
    </div>
  )
}
