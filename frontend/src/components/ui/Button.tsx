import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Link } from 'react-router-dom'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
type Size = 'md' | 'lg' | 'sm'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  block?: boolean
  loading?: boolean
}

function classes(variant: Variant, size: Size, block: boolean, extra?: string) {
  return ['btn', `btn--${variant}`, `btn--${size}`, block && 'btn--block', extra]
    .filter(Boolean)
    .join(' ')
}

export function Button({
  variant = 'primary',
  size = 'md',
  block = false,
  loading = false,
  className,
  children,
  disabled,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={classes(variant, size, block, className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading && <span className="spinner spinner--sm" aria-hidden />}
      {children}
    </button>
  )
}

interface ButtonLinkProps {
  to: string
  variant?: Variant
  size?: Size
  block?: boolean
  className?: string
  children: ReactNode
}

export function ButtonLink({
  to,
  variant = 'primary',
  size = 'md',
  block = false,
  className,
  children,
}: ButtonLinkProps) {
  return (
    <Link to={to} className={classes(variant, size, block, className)}>
      {children}
    </Link>
  )
}
