export const COLOR_SWATCHES: Record<string, string> = {
  black: '#1d1d1f',
  white: '#f4f2ed',
  gray: '#8e8e8e',
  navy: '#22304f',
  blue: '#3d5a80',
  'light blue': '#9bbbe0',
  red: '#b4282d',
  burgundy: '#6e1e2d',
  pink: '#e6a0b4',
  orange: '#e17828',
  yellow: '#e6c83c',
  beige: '#c8b593',
  brown: '#6e4b32',
  green: '#3c8246',
  olive: '#6b6a45',
  purple: '#6e468c',
}

export const COLOR_OPTIONS = Object.keys(COLOR_SWATCHES)

export function swatchFor(color: string | null | undefined): string {
  if (!color) return '#d9d4cc'
  return COLOR_SWATCHES[color.toLowerCase()] ?? '#d9d4cc'
}

/** Pick a readable foreground for a swatch background. */
export function isLight(hex: string): boolean {
  const n = Number.parseInt(hex.slice(1), 16)
  const r = (n >> 16) & 255
  const g = (n >> 8) & 255
  const b = n & 255
  return 0.299 * r + 0.587 * g + 0.114 * b > 170
}
