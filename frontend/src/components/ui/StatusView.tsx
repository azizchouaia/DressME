import type { ReactNode } from 'react'
import { Button } from './Button'

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="status-view" role="status">
      <span className="spinner" aria-hidden />
      {label && <p className="status-view__text">{label}</p>}
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="status-view status-view--error" role="alert">
      <p className="status-view__title">Something went wrong</p>
      <p className="status-view__text">{message}</p>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  )
}

export function EmptyState({
  title,
  text,
  action,
}: {
  title: string
  text?: string
  action?: ReactNode
}) {
  return (
    <div className="status-view">
      <p className="status-view__title">{title}</p>
      {text && <p className="status-view__text">{text}</p>}
      {action}
    </div>
  )
}
