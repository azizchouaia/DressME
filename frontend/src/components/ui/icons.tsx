import type { ReactNode } from 'react'

function Icon({ children, size = 24 }: { children: ReactNode; size?: number }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      {children}
    </svg>
  )
}

export const HomeIcon = () => (
  <Icon>
    <path d="M4 11l8-7 8 7v8a1 1 0 0 1-1 1h-4v-6h-6v6H5a1 1 0 0 1-1-1z" />
  </Icon>
)

export const HangerIcon = () => (
  <Icon>
    <path d="M12 7a2 2 0 1 1 2-2" />
    <path d="M12 7v2L3.5 15.5A1.5 1.5 0 0 0 4.4 18h15.2a1.5 1.5 0 0 0 .9-2.5L12 9" />
  </Icon>
)

export const LayersIcon = () => (
  <Icon>
    <path d="M12 3l9 5-9 5-9-5z" />
    <path d="M3 13l9 5 9-5" />
  </Icon>
)

export const AvatarIcon = () => (
  <Icon>
    <circle cx="12" cy="5" r="2.2" />
    <path d="M8 21v-7l-2 -1 1.5-5h9L18 13l-2 1v7" />
    <path d="M12 14v7" />
  </Icon>
)

export const UserIcon = () => (
  <Icon>
    <circle cx="12" cy="8" r="4" />
    <path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6" />
  </Icon>
)

export const PlusIcon = ({ size }: { size?: number }) => (
  <Icon size={size}>
    <path d="M12 5v14M5 12h14" />
  </Icon>
)

export const CameraIcon = () => (
  <Icon>
    <path d="M4 8h3l2-3h6l2 3h3v11H4z" />
    <circle cx="12" cy="13" r="3.5" />
  </Icon>
)

export const ImageIcon = () => (
  <Icon>
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <circle cx="9" cy="10" r="1.8" />
    <path d="M21 16l-5-5-9 9" />
  </Icon>
)

export const SparkleIcon = () => (
  <Icon>
    <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" />
    <path d="M19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z" />
  </Icon>
)

export const CubeIcon = ({ size = 14 }: { size?: number }) => (
  <Icon size={size}>
    <path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z" />
    <path d="M12 12l8-4.5M12 12v9M12 12L4 7.5" />
  </Icon>
)
