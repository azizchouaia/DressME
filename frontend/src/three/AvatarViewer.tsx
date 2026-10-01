import { ContactShadows, OrbitControls, useProgress } from '@react-three/drei'
import { Canvas } from '@react-three/fiber'
import { Suspense, useCallback, useRef, useState, type ComponentRef } from 'react'
import type { OutfitSlot } from '../types'
import { GltfModel } from './GltfModel'
import { ModelErrorBoundary } from './ModelErrorBoundary'
import './AvatarViewer.css'

export interface AvatarViewerProps {
  avatarUrl: string
  /** Applied to avatar and garments together so they stay aligned. */
  scale?: { x: number; y: number; z: number }
  /** One GLB per slot. Only these assets are loaded — never the whole wardrobe. */
  garments: Partial<Record<OutfitSlot, string | null>>
  interactive?: boolean
  className?: string
}

const SLOT_ORDER: OutfitSlot[] = ['bottom', 'shoes', 'top', 'outerwear']
const CAMERA_TARGET: [number, number, number] = [0, 0.92, 0]

export function AvatarViewer({
  avatarUrl,
  scale = { x: 1, y: 1, z: 1 },
  garments,
  interactive = true,
  className,
}: AvatarViewerProps) {
  const controls = useRef<ComponentRef<typeof OrbitControls>>(null)
  const [error, setError] = useState<string | null>(null)
  const { active, progress } = useProgress()

  const resetCamera = useCallback(() => controls.current?.reset(), [])
  const reportError = useCallback(() => setError('Part of this outfit could not be loaded.'), [])

  return (
    <div className={`avatar-viewer ${interactive ? 'is-interactive' : ''} ${className ?? ''}`}>
      <Canvas
        className="avatar-viewer__canvas"
        frameloop="demand"
        dpr={[1, 2]}
        shadows
        camera={{ position: [0, 1.15, 3.4], fov: 34, near: 0.1, far: 30 }}
        gl={{ antialias: true, alpha: true, powerPreference: 'low-power' }}
      >
        <hemisphereLight args={['#ffffff', '#d6cfc4', 1.4]} />
        <directionalLight
          position={[2.5, 4, 3]}
          intensity={1.8}
          castShadow
          shadow-mapSize={[1024, 1024]}
        />
        <directionalLight position={[-3, 2.5, -2.5]} intensity={0.7} />

        <group scale={[scale.x, scale.y, scale.z]}>
          <ModelErrorBoundary resetKey={avatarUrl} onError={reportError}>
            <Suspense fallback={null}>
              <GltfModel url={avatarUrl} disposeOnUnmount={false} />
            </Suspense>
          </ModelErrorBoundary>

          {SLOT_ORDER.map((slot) => {
            const url = garments[slot]
            if (!url) return null
            return (
              <ModelErrorBoundary key={slot} resetKey={url} onError={reportError}>
                <Suspense fallback={null}>
                  <GltfModel key={url} url={url} />
                </Suspense>
              </ModelErrorBoundary>
            )
          })}
        </group>

        <ContactShadows position={[0, 0.001, 0]} opacity={0.35} scale={3} blur={2.4} far={1.2} />

        <OrbitControls
          ref={controls}
          makeDefault
          target={CAMERA_TARGET}
          enableRotate={interactive}
          enableZoom={interactive}
          enablePan={false}
          enableDamping
          minDistance={1.4}
          maxDistance={5}
          minPolarAngle={Math.PI * 0.18}
          maxPolarAngle={Math.PI * 0.56}
        />
      </Canvas>

      {active && (
        <div className="avatar-viewer__loading" role="status">
          <span className="spinner" aria-hidden />
          <span>Loading {Math.round(progress)}%</span>
        </div>
      )}

      {error && (
        <div className="avatar-viewer__error" role="alert">
          <span>{error}</span>
          <button type="button" onClick={() => setError(null)} aria-label="Dismiss">
            ×
          </button>
        </div>
      )}

      {interactive && (
        <button type="button" className="avatar-viewer__reset" onClick={resetCamera}>
          Reset view
        </button>
      )}
    </div>
  )
}
