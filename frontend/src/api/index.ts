import type {
  AvatarConfig,
  BodyProfile,
  ClothingAnalysis,
  ClothingCategory,
  ClothingItem,
  ClothingUpdate,
  Outfit,
  OutfitInput,
  TokenResponse,
  User,
} from '../types'
import { request } from './client'

export { ApiError } from './client'

export const authApi = {
  register: (body: { email: string; password: string; display_name: string }) =>
    request<TokenResponse>('/auth/register', { method: 'POST', body }),
  login: (body: { email: string; password: string }) =>
    request<TokenResponse>('/auth/login', { method: 'POST', body }),
  demo: () => request<TokenResponse>('/auth/demo', { method: 'POST' }),
  me: () => request<User>('/users/me'),
}

export const wardrobeApi = {
  list: (category?: ClothingCategory) =>
    request<ClothingItem[]>(category ? `/wardrobe?category=${category}` : '/wardrobe'),
  get: (id: string) => request<ClothingItem>(`/wardrobe/${id}`),
  upload: (image: Blob, name?: string) => {
    const form = new FormData()
    form.append('image', image, 'photo.jpg')
    if (name) form.append('name', name)
    return request<ClothingItem>('/wardrobe/upload', { method: 'POST', form })
  },
  update: (id: string, body: ClothingUpdate) =>
    request<ClothingItem>(`/wardrobe/${id}`, { method: 'PUT', body }),
  remove: (id: string) => request<void>(`/wardrobe/${id}`, { method: 'DELETE' }),
  analyze: (id: string) => request<ClothingAnalysis>(`/wardrobe/${id}/analyze`, { method: 'POST' }),
}

export const outfitsApi = {
  list: () => request<Outfit[]>('/outfits'),
  get: (id: string) => request<Outfit>(`/outfits/${id}`),
  create: (body: OutfitInput) => request<Outfit>('/outfits', { method: 'POST', body }),
  update: (id: string, body: Partial<OutfitInput>) =>
    request<Outfit>(`/outfits/${id}`, { method: 'PUT', body }),
  remove: (id: string) => request<void>(`/outfits/${id}`, { method: 'DELETE' }),
}

export const bodyApi = {
  get: () => request<BodyProfile>('/body-profile'),
  update: (body: Omit<BodyProfile, 'source'>) =>
    request<BodyProfile>('/body-profile', { method: 'PUT', body }),
}

export const avatarApi = {
  get: () => request<AvatarConfig>('/avatar'),
}
