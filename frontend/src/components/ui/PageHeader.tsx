import type { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'

interface Props {
  title: string
  subtitle?: string
  back?: boolean
  action?: ReactNode
}

export function PageHeader({ title, subtitle, back = false, action }: Props) {
  const navigate = useNavigate()
  return (
    <header className="page-header">
      {back && (
        <button
          type="button"
          className="icon-btn"
          onClick={() => navigate(-1)}
          aria-label="Go back"
        >
          <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden>
            <path d="M15 5l-7 7 7 7" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      )}
      <div className="page-header__titles">
        <h1 className="page-header__title">{title}</h1>
        {subtitle && <p className="page-header__subtitle">{subtitle}</p>}
      </div>
      {action && <div className="page-header__action">{action}</div>}
    </header>
  )
}
