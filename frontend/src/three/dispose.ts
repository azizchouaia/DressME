import type { Material, Object3D, Texture } from 'three'
import { Mesh } from 'three'

function disposeMaterial(material: Material) {
  for (const value of Object.values(material) as unknown[]) {
    if (value && typeof value === 'object' && 'isTexture' in value) {
      ;(value as Texture).dispose()
    }
  }
  material.dispose()
}

/** Release GPU buffers for everything under `root`. */
export function disposeObject(root: Object3D) {
  root.traverse((child) => {
    if (!(child instanceof Mesh)) return
    child.geometry.dispose()
    const materials = Array.isArray(child.material) ? child.material : [child.material]
    for (const material of materials as Material[]) disposeMaterial(material)
  })
}
