import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'

const SLOT_ORDER = ['bottom', 'shoes', 'top', 'outerwear']
const PLACEMENT = {
  top: { y: 1.22, size: 0.62 },
  bottom: { y: 0.5, size: 0.9 },
  outerwear: { y: 1.18, size: 0.72 },
  shoes: { y: 0.08, size: 0.26 },
}

const loader = new GLTFLoader()
const cache = new Map()

const renderer = new THREE.WebGLRenderer({
  canvas: document.getElementById('c'),
  antialias: true,
  alpha: true,
  powerPreference: 'low-power',
})
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
renderer.setClearColor(0x000000, 0)
renderer.shadowMap.enabled = true

const scene = new THREE.Scene()
const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 30)
camera.position.set(0, 1.15, 3.4)

scene.add(new THREE.HemisphereLight(0xffffff, 0xd6cfc4, 1.4))
const keyLight = new THREE.DirectionalLight(0xffffff, 1.8)
keyLight.position.set(2.5, 4, 3)
keyLight.castShadow = true
keyLight.shadow.mapSize.set(1024, 1024)
scene.add(keyLight)
const fillLight = new THREE.DirectionalLight(0xffffff, 0.7)
fillLight.position.set(-3, 2.5, -2.5)
scene.add(fillLight)

const shadow = new THREE.Mesh(
  new THREE.CircleGeometry(0.7, 48),
  new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.18, depthWrite: false }),
)
shadow.rotation.x = -Math.PI / 2
shadow.position.y = 0.001
scene.add(shadow)

const root = new THREE.Group()
scene.add(root)

const resetButton = document.getElementById('reset')
const errorBanner = document.getElementById('error')
resetButton.addEventListener('click', () => {
  controls.reset()
  renderNow()
})

const controls = new OrbitControls(camera, renderer.domElement)
controls.target.set(0, 0.92, 0)
controls.enablePan = false
controls.enableDamping = true
controls.minDistance = 1.4
controls.maxDistance = 5
controls.minPolarAngle = Math.PI * 0.18
controls.maxPolarAngle = Math.PI * 0.56
controls.saveState()

let sceneKey = ''
let generation = 0

function loadGltf(url) {
  const cached = cache.get(url)
  if (cached) return cached
  const pending = loader.loadAsync(url)
  cache.set(url, pending)
  pending.catch(() => cache.delete(url))
  return pending
}

function resize() {
  const parent = renderer.domElement.parentElement
  const width = parent?.clientWidth || window.innerWidth
  const height = parent?.clientHeight || window.innerHeight
  renderer.setSize(width, Math.max(height, 1), false)
  camera.aspect = width / Math.max(height, 1)
  camera.updateProjectionMatrix()
}

function renderNow() {
  controls.update()
  renderer.render(scene, camera)
}

function tick() {
  requestAnimationFrame(tick)
  if (controls.enabled && controls.update()) renderer.render(scene, camera)
}

function setInteractive(on) {
  controls.enabled = on
  controls.enableRotate = on
  controls.enableZoom = on
  resetButton.hidden = !on
}

function showError(message) {
  errorBanner.hidden = !message
  errorBanner.textContent = message || ''
}

function post(data) {
  const raw = JSON.stringify(data)
  if (window.FlutterChannel) window.FlutterChannel.postMessage(raw)
  if (window.parent && window.parent !== window) window.parent.postMessage(raw, '*')
}

function clearRoot() {
  while (root.children.length) root.remove(root.children[0])
}

function prepareMeshes(object) {
  object.traverse((child) => {
    if (child.isMesh) {
      child.castShadow = true
      child.receiveShadow = true
    }
  })
}

function isTemplate(url) {
  return url.includes('/models/')
}

const HIP_Y = 0.86
const SHOULDER = { x: 0.185, y: 1.415 }
const ARM_ALONG_X = Math.sin((14 * Math.PI) / 180)
const ARM_ALONG_Y = -Math.cos((14 * Math.PI) / 180)

function clamp(value, low, high) {
  return Math.min(high, Math.max(low, value))
}

function smoothstep(value) {
  const t = clamp(value, 0, 1)
  return t * t * (3 - 2 * t)
}

function band(y, center, half) {
  return 1 - smoothstep(Math.abs(y - center) / half)
}

function deformPoint(x, y, z, shape) {
  const leg = clamp(shape.leg_length_ratio ?? 1, 0.85, 1.2)
  const arm = clamp(shape.arm_length_ratio ?? 1, 0.85, 1.2)
  const chest = clamp(shape.chest_ratio ?? 1, 0.8, 1.35)
  const waist = clamp(shape.waist_ratio ?? 1, 0.75, 1.4)
  const hips = clamp(shape.hips_ratio ?? 1, 0.8, 1.35)
  const shoulder = clamp(shape.shoulder_width_ratio ?? 1, 0.85, 1.3)
  const depth = clamp(shape.depth_ratio ?? 1, 0.85, 1.2)
  const side = x >= 0 ? 1 : -1
  const ox = x - side * SHOULDER.x
  const oy = y - SHOULDER.y
  const axisX = side * ARM_ALONG_X
  const along = ox * axisX + oy * ARM_ALONG_Y
  const px = ox - along * axisX
  const py = oy - along * ARM_ALONG_Y
  const perp = Math.hypot(px, py, z)
  const inTorso = y > 0.82 && y < 1.5 && (x * x) / 0.04 + (z * z) / 0.0196 < 1
  const onArm = !inTorso && along > 0.03 && perp < 0.14 && y < 1.46 && y > 0.5 && Math.abs(x) > 0.12
  const lift = HIP_Y * (leg - 1)

  if (onArm) {
    const jointX = side * SHOULDER.x * (1 + (shoulder - 1) * 0.85)
    const stretched = along * arm
    return [
      jointX + stretched * axisX + px,
      SHOULDER.y + lift + stretched * ARM_ALONG_Y + py,
      z,
    ]
  }

  const vy = y < HIP_Y ? y * leg : HIP_Y * leg + (y - HIP_Y)
  const head = smoothstep((y - 1.5) / 0.12)
  const influence = 1 - head
  const radialX =
    1 +
    influence *
      ((hips - 1) * band(y, 0.9, 0.14) +
        (waist - 1) * band(y, 1.06, 0.12) +
        (chest - 1) * band(y, 1.26, 0.14) +
        (shoulder - 1) * band(y, 1.4, 0.1))
  const radialZ =
    1 +
    influence *
      ((depth - 1) * 0.85 +
        (hips - 1) * 0.35 * band(y, 0.9, 0.14) +
        (waist - 1) * 0.35 * band(y, 1.06, 0.12) +
        (chest - 1) * 0.25 * band(y, 1.26, 0.14))
  return [x * radialX, vy, z * radialZ]
}

function shapeTemplate(object, shape) {
  object.traverse((child) => {
    if (!child.isMesh || !child.geometry?.attributes?.position) return
    const geometry = child.geometry.clone()
    const position = geometry.attributes.position
    for (let index = 0; index < position.count; index += 1) {
      const next = deformPoint(position.getX(index), position.getY(index), position.getZ(index), shape)
      position.setXYZ(index, next[0], next[1], next[2])
    }
    position.needsUpdate = true
    geometry.computeVertexNormals()
    child.geometry = geometry
  })
}

function fitStanding(object) {
  object.updateMatrixWorld(true)
  const box = new THREE.Box3().setFromObject(object)
  const size = box.getSize(new THREE.Vector3())
  const factor = 1.75 / Math.max(size.y, 0.001)
  object.scale.multiplyScalar(factor)
  object.updateMatrixWorld(true)
  const fitted = new THREE.Box3().setFromObject(object)
  const center = fitted.getCenter(new THREE.Vector3())
  object.position.x -= center.x
  object.position.z -= center.z
  object.position.y -= fitted.min.y
}

function fitSlot(object, slot) {
  const place = PLACEMENT[slot]
  object.updateMatrixWorld(true)
  const box = new THREE.Box3().setFromObject(object)
  const size = box.getSize(new THREE.Vector3())
  const center = box.getCenter(new THREE.Vector3())
  const longest = Math.max(size.x, size.y, size.z, 0.001)
  const scale = place.size / longest
  const wrap = new THREE.Group()
  wrap.position.set(-center.x * scale, place.y - center.y * scale, -center.z * scale)
  wrap.scale.setScalar(scale)
  wrap.add(object)
  return wrap
}

function useAvatarCamera() {
  camera.fov = 34
  camera.near = 0.1
  camera.far = 30
  camera.position.set(0, 1.15, 3.4)
  controls.target.set(0, 0.92, 0)
  controls.minDistance = 1.4
  controls.maxDistance = 5
  controls.minPolarAngle = Math.PI * 0.18
  controls.maxPolarAngle = Math.PI * 0.56
  camera.updateProjectionMatrix()
  controls.update()
  controls.saveState()
}

function useMeshCamera() {
  camera.fov = 40
  camera.near = 0.01
  camera.far = 20
  camera.position.set(0, 0.2, 2.4)
  controls.target.set(0, 0, 0)
  controls.minDistance = 0.4
  controls.maxDistance = 8
  controls.minPolarAngle = 0
  controls.maxPolarAngle = Math.PI
  camera.updateProjectionMatrix()
  controls.update()
  controls.saveState()
}

async function applyAvatar(message) {
  const scale = message.scale || { x: 1, y: 1, z: 1 }
  const garments = message.garments || {}
  const shape = message.shape || {}
  const key = JSON.stringify({ mode: 'avatar', avatar: message.avatarUrl, scale, garments, shape })
  const interactive = message.interactive !== false
  setInteractive(interactive)
  if (key === sceneKey) {
    renderNow()
    return
  }
  const switchingMode = !sceneKey.startsWith('{"mode":"avatar"')
  sceneKey = key
  const token = ++generation
  if (switchingMode) useAvatarCamera()

  showError('')
  clearRoot()
  const group = new THREE.Group()
  group.scale.set(scale.x ?? 1, scale.y ?? 1, scale.z ?? 1)
  root.add(group)

  let failed = false
  try {
    const avatar = await loadGltf(message.avatarUrl)
    if (token !== generation) return
    const object = avatar.scene.clone(true)
    prepareMeshes(object)
    const photoBody = !isTemplate(message.avatarUrl)
    if (photoBody) fitStanding(object)
    else shapeTemplate(object, shape)
    group.add(object)
    if (photoBody) {
      if (token !== generation) return
      renderNow()
      return
    }
  } catch {
    failed = true
  }

  for (const slot of SLOT_ORDER) {
    const url = garments[slot]
    if (!url) continue
    try {
      const gltf = await loadGltf(url)
      if (token !== generation) return
      const object = gltf.scene.clone(true)
      prepareMeshes(object)
      if (isTemplate(url)) shapeTemplate(object, shape)
      group.add(isTemplate(url) ? object : fitSlot(object, slot))
    } catch {
      failed = true
    }
  }

  if (token !== generation) return
  if (failed) showError('Part of this outfit could not be loaded.')
  renderNow()
}

async function applyMesh(message) {
  const key = JSON.stringify({ mode: 'mesh', url: message.url })
  setInteractive(true)
  if (key === sceneKey) {
    renderNow()
    return
  }
  sceneKey = key
  const token = ++generation
  useMeshCamera()
  showError('')
  clearRoot()
  try {
    const gltf = await loadGltf(message.url)
    if (token !== generation) return
    const object = gltf.scene.clone(true)
    prepareMeshes(object)
    object.updateMatrixWorld(true)
    const box = new THREE.Box3().setFromObject(object)
    const size = box.getSize(new THREE.Vector3())
    const center = box.getCenter(new THREE.Vector3())
    const longest = Math.max(size.x, size.y, size.z, 0.001)
    const scale = 1.2 / longest
    object.position.set(-center.x * scale, -center.y * scale, -center.z * scale)
    object.scale.setScalar(scale)
    root.add(object)
  } catch {
    showError('This preview could not be shown.')
  }
  if (token !== generation) return
  renderNow()
}

function applyScene(message) {
  if (!message || message.type !== 'scene') return
  if (message.mode === 'mesh') applyMesh(message)
  else applyAvatar(message)
}

window.__applyScene = (message) => {
  const data = typeof message === 'string' ? JSON.parse(message) : message
  if (data?.type === 'reset') {
    controls.reset()
    renderNow()
    return
  }
  applyScene(data)
}

window.addEventListener('message', (event) => {
  let data = event.data
  if (typeof data === 'string') {
    try {
      data = JSON.parse(data)
    } catch {
      return
    }
  }
  window.__applyScene(data)
})

window.addEventListener('resize', () => {
  resize()
  renderNow()
})

resize()
tick()
renderNow()
post({ type: 'ready' })
