import { useGLTF } from '@react-three/drei'
import { useEffect } from 'react'
import { Mesh } from 'three'
import { disposeObject } from './dispose'

interface Props {
  url: string
  /** Free GPU memory and drop the cache entry once this model leaves the scene. */
  disposeOnUnmount?: boolean
}

export function GltfModel({ url, disposeOnUnmount = true }: Props) {
  const { scene } = useGLTF(url)

  useEffect(() => {
    scene.traverse((child) => {
      if (child instanceof Mesh) {
        child.castShadow = true
        child.receiveShadow = true
      }
    })
  }, [scene])

  useEffect(() => {
    if (!disposeOnUnmount) return
    return () => {
      disposeObject(scene)
      useGLTF.clear(url)
    }
  }, [scene, url, disposeOnUnmount])

  return <primitive object={scene} />
}
