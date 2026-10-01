import { avatarApi } from '../../api'
import { useResource } from '../../hooks/useResource'
import type { AvatarConfig } from '../../types'

export const DEFAULT_AVATAR: AvatarConfig = {
  base_model_url: '/models/avatar/base_avatar.glb',
  preset: 'average',
  scale: { x: 1, y: 1, z: 1 },
  parameters: {},
}

/** Falls back to the default avatar so the 3D view still works if the request fails. */
export function useAvatarConfig(): AvatarConfig {
  const { data } = useResource(() => avatarApi.get(), [])
  return data ?? DEFAULT_AVATAR
}
