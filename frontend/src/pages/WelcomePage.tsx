import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authApi } from '../api'
import { Button, ButtonLink } from '../components/ui/Button'
import { useAuthStore } from '../stores/authStore'
import { AvatarViewer } from '../three/AvatarViewer'

const PREVIEW_GARMENTS = {
  top: '/models/garments/black_tshirt.glb',
  bottom: '/models/garments/blue_jeans.glb',
  outerwear: '/models/garments/black_jacket.glb',
  shoes: '/models/garments/white_sneakers.glb',
}

export function WelcomePage() {
  const navigate = useNavigate()
  const setSession = useAuthStore((s) => s.setSession)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const tryDemo = async () => {
    setLoading(true)
    setError(null)
    try {
      const session = await authApi.demo()
      setSession(session.access_token, session.user)
      navigate('/avatar')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Demo is unavailable right now.')
      setLoading(false)
    }
  }

  return (
    <div className="welcome">
      <div className="welcome__stage">
        <AvatarViewer
          avatarUrl="/models/avatar/base_avatar.glb"
          garments={PREVIEW_GARMENTS}
          interactive={false}
        />
      </div>
      <div className="welcome__content">
        <p className="eyebrow">Smart Wardrobe</p>
        <h1 className="display">Your real clothes, on your own avatar.</h1>
        <p className="lede">
          Photograph what you own, build outfits, and see them on a 3D model before you get
          dressed.
        </p>
        <div className="stack">
          <ButtonLink to="/register" size="lg" block>
            Create account
          </ButtonLink>
          <ButtonLink to="/login" variant="secondary" size="lg" block>
            I already have an account
          </ButtonLink>
          <Button variant="ghost" block loading={loading} onClick={tryDemo}>
            Explore the demo wardrobe
          </Button>
          {error && <p className="form-error">{error}</p>}
        </div>
      </div>
    </div>
  )
}
