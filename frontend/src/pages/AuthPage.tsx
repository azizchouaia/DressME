import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { authApi } from '../api'
import { Button } from '../components/ui/Button'
import { TextField } from '../components/ui/Field'
import { PageHeader } from '../components/ui/PageHeader'
import { useAuthStore } from '../stores/authStore'

export function AuthPage({ mode }: { mode: 'login' | 'register' }) {
  const navigate = useNavigate()
  const location = useLocation()
  const setSession = useAuthStore((s) => s.setSession)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const isRegister = mode === 'register'

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const session = isRegister
        ? await authApi.register({ email, password, display_name: name.trim() })
        : await authApi.login({ email, password })
      setSession(session.access_token, session.user)
      const from = (location.state as { from?: string } | null)?.from
      navigate(from ?? '/home', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
      setSubmitting(false)
    }
  }

  return (
    <div className="auth">
      <PageHeader
        back
        title={isRegister ? 'Create your wardrobe' : 'Welcome back'}
        subtitle={
          isRegister
            ? 'We’ll start you with a few sample pieces to try on.'
            : 'Sign in to see your wardrobe and outfits.'
        }
      />
      <form className="form" onSubmit={onSubmit}>
        {isRegister && (
          <TextField
            label="First name"
            autoComplete="given-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            maxLength={80}
          />
        )}
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          inputMode="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <TextField
          label="Password"
          type="password"
          autoComplete={isRegister ? 'new-password' : 'current-password'}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          minLength={isRegister ? 8 : undefined}
          hint={isRegister ? 'At least 8 characters' : undefined}
          required
        />
        {error && <p className="form-error">{error}</p>}
        <Button type="submit" size="lg" block loading={submitting}>
          {isRegister ? 'Create account' : 'Sign in'}
        </Button>
        <p className="auth__switch">
          {isRegister ? 'Already have an account? ' : 'New here? '}
          <Link to={isRegister ? '/login' : '/register'}>
            {isRegister ? 'Sign in' : 'Create an account'}
          </Link>
        </p>
      </form>
    </div>
  )
}
