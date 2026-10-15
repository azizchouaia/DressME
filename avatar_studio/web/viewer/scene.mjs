import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'

const canvas = document.getElementById('c')
const errorNode = document.getElementById('error')
const resetButton = document.getElementById('reset')
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true })
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
renderer.setClearColor(0x000000, 0)

const scene = new THREE.Scene()
scene.add(new THREE.HemisphereLight(0xfff8f2, 0xb7aea4, 0.85))
const key = new THREE.DirectionalLight(0xfff6ee, 1.05)
key.position.set(2.4, 4, 3)
scene.add(key)

const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 30)
camera.position.set(0, 0.95, 5.4)
const controls = new OrbitControls(camera, canvas)
controls.target.set(0, 0.84, 0)
controls.enableDamping = true
controls.minDistance = 1.2
controls.maxDistance = 6
controls.update()
controls.saveState()

const loader = new GLTFLoader()
const group = new THREE.Group()
scene.add(group)

const mannequin = new THREE.MeshStandardMaterial({
  color: 0xd8cfc6,
  roughness: 0.62,
  metalness: 0.02,
})

let shownUrl = ''
let loadToken = 0
let rig = null
let skeletonHelper = null
let restHeight = 1.7
let photoSex = 'auto'
let applyingPreset = false
let hairChoice = 'brown'
let eyeChoice = 'hazel'
let skinChoice = 'light'
let buildBase = ''
let buildRequest = 0

const hairColors = {
  black: '#1a120e',
  brown: '#5c3a24',
  red: '#8d3b24',
  blonde: '#d7b56a',
}
const skinColors = {
  fair: '#f6d7c8',
  light: '#b9aea3',
  warm: '#d2a07a',
  tan: '#a56b45',
  brown: '#6b4032',
  deep: '#3e271e',
}
const eyeColors = {
  hazel: '#8a6a3b',
  black: '#1c140f',
  green: '#3d6b45',
  blue: '#3d6f9a',
}

const posePresets = {
  tpose: {},
  stand: { armL: -75, armR: -75, elbowL: 8, elbowR: 8 },
  hips: { armL: -36, armR: -36, elbowL: 100, elbowR: 100, armInL: 48, armInR: 48 },
  step: { armL: -80, armR: -45, legL: 32, legR: -10, kneeL: 22, elbowR: 12 },
  wave: { armL: 62, armR: -75, elbowL: 28, elbowR: 8 },
}

function resize() {
  const width = canvas.clientWidth || 1
  const height = canvas.clientHeight || 1
  const pixelWidth = Math.floor(width * renderer.getPixelRatio())
  const pixelHeight = Math.floor(height * renderer.getPixelRatio())
  if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) renderer.setSize(width, height, false)
  const bar = document.querySelector('.build-bar')
  const sheet = document.querySelector('.sheet')
  const top = bar ? bar.getBoundingClientRect().bottom : 0
  const bottom = sheet && !sheet.hidden ? Math.max(0, height - sheet.getBoundingClientRect().top) : 0
  const freeCenter = top + (height - top - bottom) / 2
  const shift = height / 2 - freeCenter
  camera.aspect = width / height
  camera.setViewOffset(width, height, 0, -shift * 0.2, width, height)
  camera.updateProjectionMatrix()
}

function showError(message) {
  errorNode.hidden = !message
  errorNode.textContent = message || ''
}

function fitStanding(object) {
  object.rotation.set(0, 0, 0)
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

function addBone(parent, name, world) {
  const bone = new THREE.Bone()
  bone.name = name
  if (parent) {
    parent.add(bone)
    parent.updateWorldMatrix(true, false)
    bone.position.copy(parent.worldToLocal(world.clone()))
  } else {
    bone.position.copy(world)
  }
  return bone
}

let bodySex = 'female'
let bodyMeasures = null

function percentile(values, t) {
  if (!values.length) return 0
  const sorted = values.slice().sort((a, b) => a - b)
  return sorted[Math.min(sorted.length - 1, Math.floor(t * (sorted.length - 1)))]
}

function band(geometry, y0, y1) {
  const position = geometry.attributes.position
  const point = new THREE.Vector3()
  const xs = []
  const zs = []
  for (let i = 0; i < position.count; i += 1) {
    point.fromBufferAttribute(position, i)
    if (point.y < y0 || point.y >= y1) continue
    xs.push(Math.abs(point.x))
    zs.push(Math.abs(point.z))
  }
  if (xs.length < 24) return null
  return { halfX: percentile(xs, 0.86), halfZ: percentile(zs, 0.86) }
}

function measureBody(geometry) {
  geometry.computeBoundingBox()
  const box = geometry.boundingBox
  const minY = box.min.y
  const height = Math.max(box.max.y - minY, 0.001)
  const slice = (a, b) => band(geometry, minY + height * a, minY + height * b)
  const shoulder = slice(0.74, 0.83) || { halfX: height * 0.18, halfZ: height * 0.08 }
  const chest = slice(0.66, 0.75) || shoulder
  const waist = slice(0.56, 0.65) || chest
  const hip = slice(0.46, 0.55) || waist
  const position = geometry.attributes.position
  const point = new THREE.Vector3()
  let handY = minY + height * 0.45
  for (let i = 0; i < position.count; i += 1) {
    point.fromBufferAttribute(position, i)
    const ny = (point.y - minY) / height
    if (ny > 0.35 && ny < 0.8 && Math.abs(point.x) > shoulder.halfX * 0.72) handY = Math.min(handY, point.y)
  }
  const shoulderY = minY + height * 0.78
  const armLength = Math.min(height * 0.46, Math.max(height * 0.3, shoulderY - handY))
  const shoulderHalf = Math.min(height * 0.22, Math.max(height * 0.11, shoulder.halfX * 0.62))
  const hipHalf = Math.min(height * 0.16, Math.max(height * 0.09, hip.halfX * 0.82))
  const waistHalf = Math.min(hipHalf, Math.max(height * 0.07, Math.min(waist.halfX, chest.halfX) * 0.72))
  return {
    height,
    minY,
    shoulderHalf,
    chestHalf: Math.min(shoulderHalf, Math.max(waistHalf, chest.halfX * 0.7)),
    chestDepth: Math.min(height * 0.12, Math.max(height * 0.06, chest.halfZ * 0.9)),
    waistHalf,
    hipHalf,
    hipY: minY + height * 0.52,
    waistY: minY + height * 0.62,
    chestY: minY + height * 0.73,
    shoulderY,
    neckY: minY + height * 0.84,
    headY: minY + height * 0.9,
    armLength,
    hint: hip.halfX > shoulder.halfX * 0.9 ? 'female' : 'male',
  }
}

function shapeFor(measures, sex) {
  const shaped = { ...measures, sex }
  if (sex === 'female') {
    shaped.shoulderHalf *= 0.94
    shaped.waistHalf *= 0.82
    shaped.hipHalf *= 1.08
    shaped.chestDepth *= 1.08
  } else {
    shaped.shoulderHalf *= 1.06
    shaped.waistHalf *= 1.05
    shaped.hipHalf *= 0.94
    shaped.chestDepth *= 0.96
  }
  return shaped
}

function ringAxes(axis) {
  const direction = axis.clone().normalize()
  const side = Math.abs(direction.dot(new THREE.Vector3(1, 0, 0))) > 0.85 ? new THREE.Vector3(0, 0, 1) : new THREE.Vector3(1, 0, 0)
  const zAxis = new THREE.Vector3().crossVectors(direction, side).normalize()
  const xAxis = new THREE.Vector3().crossVectors(zAxis, direction).normalize()
  return { xAxis, zAxis }
}

function buildFigure(measures) {
  const height = measures.height
  const upperArm = measures.armLength * 0.46
  const forearm = measures.armLength * 0.38
  const hand = measures.armLength * 0.16
  const leg = measures.hipY - measures.minY
  const thigh = leg * 0.52
  const shin = leg * 0.42
  const hips = addBone(null, 'hips', new THREE.Vector3(0, measures.hipY, 0))
  const spine = addBone(hips, 'spine', new THREE.Vector3(0, measures.waistY, 0))
  const chest = addBone(spine, 'chest', new THREE.Vector3(0, measures.chestY, 0))
  const neck = addBone(chest, 'neck', new THREE.Vector3(0, measures.neckY, 0))
  const head = addBone(neck, 'head', new THREE.Vector3(0, measures.headY, 0))
  const shoulderL = addBone(chest, 'shoulderL', new THREE.Vector3(measures.shoulderHalf * 0.95, measures.shoulderY, 0))
  const upperArmL = addBone(shoulderL, 'upperArmL', new THREE.Vector3(measures.shoulderHalf * 0.95, measures.shoulderY, 0))
  const forearmL = addBone(upperArmL, 'forearmL', new THREE.Vector3(measures.shoulderHalf * 0.95, measures.shoulderY - upperArm, 0))
  const handL = addBone(forearmL, 'handL', new THREE.Vector3(measures.shoulderHalf * 0.95, measures.shoulderY - upperArm - forearm, 0))
  const shoulderR = addBone(chest, 'shoulderR', new THREE.Vector3(-measures.shoulderHalf * 0.95, measures.shoulderY, 0))
  const upperArmR = addBone(shoulderR, 'upperArmR', new THREE.Vector3(-measures.shoulderHalf * 0.95, measures.shoulderY, 0))
  const forearmR = addBone(upperArmR, 'forearmR', new THREE.Vector3(-measures.shoulderHalf * 0.95, measures.shoulderY - upperArm, 0))
  const handR = addBone(forearmR, 'handR', new THREE.Vector3(-measures.shoulderHalf * 0.95, measures.shoulderY - upperArm - forearm, 0))
  const hipX = measures.hipHalf * 0.42
  const upperLegL = addBone(hips, 'upperLegL', new THREE.Vector3(hipX, measures.hipY, 0))
  const lowerLegL = addBone(upperLegL, 'lowerLegL', new THREE.Vector3(hipX, measures.hipY - thigh, 0))
  const ankleY = measures.hipY - thigh - shin
  const footL = addBone(lowerLegL, 'footL', new THREE.Vector3(hipX, ankleY, 0))
  const upperLegR = addBone(hips, 'upperLegR', new THREE.Vector3(-hipX, measures.hipY, 0))
  const lowerLegR = addBone(upperLegR, 'lowerLegR', new THREE.Vector3(-hipX, measures.hipY - thigh, 0))
  const footR = addBone(lowerLegR, 'footR', new THREE.Vector3(-hipX, ankleY, 0))
  upperArmL.rotation.z = Math.PI / 2
  upperArmR.rotation.z = -Math.PI / 2

  const bones = [
    hips, spine, chest, neck, head,
    shoulderL, upperArmL, forearmL, handL,
    shoulderR, upperArmR, forearmR, handR,
    upperLegL, lowerLegL, footL,
    upperLegR, lowerLegR, footR,
  ]
  hips.updateWorldMatrix(true, true)
  const world = (bone) => bone.getWorldPosition(new THREE.Vector3())
  const positions = []
  const indices = []
  const skinIndex = []
  const skinWeight = []
  const radial = 16

  function addRing(center, axis, rx, rz, bone, blendBone, blend) {
    const start = positions.length / 3
    const { xAxis, zAxis } = ringAxes(axis)
    for (let i = 0; i < radial; i += 1) {
      const angle = (i / radial) * Math.PI * 2
      const point = center.clone()
        .addScaledVector(xAxis, Math.cos(angle) * rx)
        .addScaledVector(zAxis, Math.sin(angle) * rz)
      positions.push(point.x, point.y, point.z)
      skinIndex.push(bones.indexOf(bone), blendBone ? bones.indexOf(blendBone) : 0, 0, 0)
      skinWeight.push(blend, blendBone ? 1 - blend : 0, 0, 0)
    }
    return start
  }

  function connect(a, b) {
    for (let i = 0; i < radial; i += 1) {
      const next = (i + 1) % radial
      indices.push(a + i, b + i, a + next, a + next, b + i, b + next)
    }
  }

  function tube(from, to, radiusA, radiusB, bone, steps = 5) {
    const axis = to.clone().sub(from)
    const direction = axis.clone().normalize()
    const start = from.clone().addScaledVector(direction, -Math.min(radiusA * 0.8, axis.length() * 0.2))
    let previous = null
    for (let step = 0; step <= steps; step += 1) {
      const t = step / steps
      const center = start.clone().lerp(to, t)
      const radius = radiusA + (radiusB - radiusA) * t
      const ring = addRing(center, axis, radius, radius * 0.92, bone, null, 1)
      if (previous !== null) connect(previous, ring)
      previous = ring
    }
  }

  const torsoKeys = [
    { y: measures.hipY, rx: measures.hipHalf * 0.95, rz: measures.chestDepth * 0.85, bone: hips },
    { y: measures.waistY, rx: measures.waistHalf, rz: measures.chestDepth * 0.72, bone: spine },
    { y: measures.chestY, rx: measures.chestHalf, rz: measures.chestDepth, bone: chest },
    { y: measures.shoulderY, rx: measures.shoulderHalf * 0.48, rz: measures.chestDepth * 0.62, bone: chest },
    { y: measures.neckY, rx: height * 0.038, rz: height * 0.034, bone: neck },
  ]
  let previousRing = null
  let previousBone = null
  torsoKeys.forEach((key, index) => {
    const steps = index === 0 ? 1 : 4
    const before = torsoKeys[index - 1]
    for (let step = index === 0 ? 0 : 1; step <= steps; step += 1) {
      const t = index === 0 ? 0 : step / steps
      const y = before ? before.y + (key.y - before.y) * t : key.y
      const rx = before ? before.rx + (key.rx - before.rx) * t : key.rx
      const rz = before ? before.rz + (key.rz - before.rz) * t : key.rz
      const blend = t > 0.55 && before ? t : 1
      const blendBone = t > 0.55 && previousBone && previousBone !== key.bone ? previousBone : null
      const ring = addRing(new THREE.Vector3(0, y, 0), new THREE.Vector3(0, 1, 0), rx, rz, key.bone, blendBone, blendBone ? blend : 1)
      if (previousRing !== null) connect(previousRing, ring)
      previousRing = ring
    }
    previousBone = key.bone
  })

  const crown = world(head)
  const headRadius = height * (measures.sex === 'female' ? 0.072 : 0.076)
  let headRing = null
  for (let step = 1; step <= 7; step += 1) {
    const phi = -Math.PI / 2 + (step / 8) * Math.PI
    const ring = addRing(
      new THREE.Vector3(0, crown.y + Math.sin(phi) * headRadius * 1.05, 0),
      new THREE.Vector3(0, 1, 0),
      Math.cos(phi) * headRadius * 0.86,
      Math.cos(phi) * headRadius * 0.94,
      head,
      null,
      1,
    )
    if (headRing !== null) connect(headRing, ring)
    headRing = ring
  }

  const armRadius = height * (measures.sex === 'female' ? 0.032 : 0.036)
  const leftShoulder = world(upperArmL)
  const rightShoulder = world(upperArmR)
  tube(new THREE.Vector3(measures.shoulderHalf * 0.28, leftShoulder.y, 0), world(forearmL), armRadius * 1.2, armRadius * 0.95, upperArmL)
  tube(world(forearmL), world(handL), armRadius * 0.9, armRadius * 0.72, forearmL)
  tube(world(handL), world(handL).clone().add(new THREE.Vector3(hand, 0, 0)), armRadius * 0.7, armRadius * 0.45, handL, 3)
  tube(new THREE.Vector3(-measures.shoulderHalf * 0.28, rightShoulder.y, 0), world(forearmR), armRadius * 1.2, armRadius * 0.95, upperArmR)
  tube(world(forearmR), world(handR), armRadius * 0.9, armRadius * 0.72, forearmR)
  tube(world(handR), world(handR).clone().add(new THREE.Vector3(-hand, 0, 0)), armRadius * 0.7, armRadius * 0.45, handR, 3)

  const thighRadius = Math.max(height * 0.045, measures.hipHalf * 0.38)
  const shinRadius = thighRadius * 0.72
  tube(world(upperLegL), world(lowerLegL), thighRadius, thighRadius * 0.82, upperLegL)
  tube(world(lowerLegL), world(footL), shinRadius, shinRadius * 0.78, lowerLegL)
  tube(world(upperLegR), world(lowerLegR), thighRadius, thighRadius * 0.82, upperLegR)
  tube(world(lowerLegR), world(footR), shinRadius, shinRadius * 0.78, lowerLegR)
  const footReach = height * 0.1
  tube(world(footL), world(footL).add(new THREE.Vector3(0, -height * 0.015, footReach)), shinRadius * 0.7, shinRadius * 0.45, footL, 3)
  tube(world(footR), world(footR).add(new THREE.Vector3(0, -height * 0.015, footReach)), shinRadius * 0.7, shinRadius * 0.45, footR, 3)

  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
  geometry.setAttribute('skinIndex', new THREE.Uint16BufferAttribute(skinIndex, 4))
  geometry.setAttribute('skinWeight', new THREE.Float32BufferAttribute(skinWeight, 4))
  geometry.setIndex(indices)
  geometry.computeVertexNormals()
  const mesh = new THREE.SkinnedMesh(geometry, mannequin)
  mesh.add(hips)
  mesh.updateMatrixWorld(true)
  mesh.bind(new THREE.Skeleton(bones), mesh.matrixWorld)
  mesh.normalizeSkinWeights()
  mesh.frustumCulled = false
  mesh.castShadow = true
  mesh.receiveShadow = true
  return { mesh, spine, neck, upperArmL, forearmL, upperArmR, forearmR, lowerLegL, lowerLegR }
}

function showBody() {
  if (!bodyMeasures) return
  while (group.children.length) group.remove(group.children[0])
  rig = buildFigure(shapeFor(bodyMeasures, bodySex))
  group.add(rig.mesh)
  skeletonHelper = new THREE.SkeletonHelper(rig.mesh)
  skeletonHelper.visible = document.getElementById('skeleton')?.checked !== false
  group.add(skeletonHelper)
  document.querySelectorAll('[data-sex]').forEach((button) => {
    button.classList.toggle('active', button.dataset.sex === bodySex)
  })
  const fit = document.getElementById('fit')
  if (fit) {
    const shoulders = (bodyMeasures.shoulderHalf * 2).toFixed(2)
    const hips = (bodyMeasures.hipHalf * 2).toFixed(2)
    const arms = bodyMeasures.armLength.toFixed(2)
    fit.textContent = `${bodySex === 'female' ? 'Female' : 'Male'} shape · shoulders ${shoulders} m · hips ${hips} m · arms ${arms} m`
  }
  applyPose()
  resetButton.hidden = false
  render()
}

function _replacedSegmentDistance(point, start, end) {
  const line = end.clone().sub(start)
  const lengthSq = Math.max(line.lengthSq(), 1e-8)
  const t = Math.min(1, Math.max(0, point.clone().sub(start).dot(line) / lengthSq))
  return point.distanceTo(start.clone().add(line.multiplyScalar(t)))
}

function skinToBones(geometry, bones, segments) {
  const position = geometry.attributes.position
  const index = new Uint16Array(position.count * 4)
  const weight = new Float32Array(position.count * 4)
  const point = new THREE.Vector3()
  const sigma = 0.05
  for (let i = 0; i < position.count; i += 1) {
    point.fromBufferAttribute(position, i)
    const scored = segments.map((segment) => ({
      segment,
      distance: segmentDistance(point, segment.start, segment.end),
    }))
    const core = scored.filter((item) => item.segment.core).sort((a, b) => a.distance - b.distance)[0]
    const limb = scored.filter((item) => !item.segment.core).sort((a, b) => a.distance - b.distance)[0]
    let pool = scored.filter((item) => item.segment.core)
    if (limb && limb.distance < 0.075 && limb.distance + 0.02 < core.distance) {
      const name = limb.segment.bone.name
      const side = name.endsWith('L') ? 'L' : 'R'
      const arm = name.includes('Arm') || name.includes('hand')
      pool = scored.filter((item) => {
        if (item.segment.core) return item.distance < limb.distance + 0.035
        const boneName = item.segment.bone.name
        const sameFamily = arm ? boneName.includes('Arm') || boneName.includes('hand') : boneName.includes('Leg') || boneName.includes('foot')
        return sameFamily && boneName.endsWith(side)
      })
    }
    pool.forEach((item) => {
      item.score = Math.exp(-(item.distance * item.distance) / (sigma * sigma))
    })
    pool.sort((a, b) => b.score - a.score)
    const chosen = pool.slice(0, 4)
    const total = chosen.reduce((sum, item) => sum + item.score, 0) || 1
    for (let slot = 0; slot < 4; slot += 1) {
      const item = chosen[slot]
      index[i * 4 + slot] = item ? bones.indexOf(item.segment.bone) : 0
      weight[i * 4 + slot] = item ? item.score / total : 0
    }
  }
  geometry.setAttribute('skinIndex', new THREE.Uint16BufferAttribute(index, 4))
  geometry.setAttribute('skinWeight', new THREE.Float32BufferAttribute(weight, 4))
  geometry.computeVertexNormals()
}

function buildRig(geometry, bounds) {
  const height = Math.max(bounds.max.y - bounds.min.y, 0.001)
  const y = (fraction) => bounds.min.y + height * fraction
  const halfWidth = Math.max(bounds.max.x, -bounds.min.x, 0.16)
  const shoulderX = Math.min(halfWidth * 0.82, height * 0.23)
  const hipX = Math.min(halfWidth * 0.38, height * 0.11)

  const hips = addBone(null, 'hips', new THREE.Vector3(0, y(0.53), 0))
  const spine = addBone(hips, 'spine', new THREE.Vector3(0, y(0.63), 0))
  const chest = addBone(spine, 'chest', new THREE.Vector3(0, y(0.75), 0))
  const neck = addBone(chest, 'neck', new THREE.Vector3(0, y(0.84), 0))
  const head = addBone(neck, 'head', new THREE.Vector3(0, y(0.9), 0))

  const shoulderL = addBone(chest, 'shoulderL', new THREE.Vector3(shoulderX * 0.72, y(0.78), 0))
  const upperArmL = addBone(shoulderL, 'upperArmL', new THREE.Vector3(shoulderX, y(0.76), 0))
  const forearmL = addBone(upperArmL, 'forearmL', new THREE.Vector3(shoulderX, y(0.6), 0))
  const handL = addBone(forearmL, 'handL', new THREE.Vector3(shoulderX, y(0.46), 0))

  const shoulderR = addBone(chest, 'shoulderR', new THREE.Vector3(-shoulderX * 0.72, y(0.78), 0))
  const upperArmR = addBone(shoulderR, 'upperArmR', new THREE.Vector3(-shoulderX, y(0.76), 0))
  const forearmR = addBone(upperArmR, 'forearmR', new THREE.Vector3(-shoulderX, y(0.6), 0))
  const handR = addBone(forearmR, 'handR', new THREE.Vector3(-shoulderX, y(0.46), 0))

  const upperLegL = addBone(hips, 'upperLegL', new THREE.Vector3(hipX, y(0.51), 0))
  const lowerLegL = addBone(upperLegL, 'lowerLegL', new THREE.Vector3(hipX, y(0.27), 0))
  const footL = addBone(lowerLegL, 'footL', new THREE.Vector3(hipX, y(0.045), 0))

  const upperLegR = addBone(hips, 'upperLegR', new THREE.Vector3(-hipX, y(0.51), 0))
  const lowerLegR = addBone(upperLegR, 'lowerLegR', new THREE.Vector3(-hipX, y(0.27), 0))
  const footR = addBone(lowerLegR, 'footR', new THREE.Vector3(-hipX, y(0.045), 0))

  const point = (x, yPos, z = 0) => new THREE.Vector3(x, yPos, z)
  const segments = [
    { bone: hips, core: true, start: point(-hipX, y(0.51)), end: point(hipX, y(0.51)) },
    { bone: spine, core: true, start: point(0, y(0.53)), end: point(0, y(0.63)) },
    { bone: chest, core: true, start: point(0, y(0.63)), end: point(0, y(0.8)) },
    { bone: neck, core: true, start: point(0, y(0.8)), end: point(0, y(0.9)) },
    { bone: head, core: true, start: point(0, y(0.9)), end: point(0, y(1.02)) },
    { bone: upperArmL, core: false, start: point(shoulderX, y(0.76)), end: point(shoulderX, y(0.6)) },
    { bone: forearmL, core: false, start: point(shoulderX, y(0.6)), end: point(shoulderX, y(0.46)) },
    { bone: handL, core: false, start: point(shoulderX, y(0.46)), end: point(shoulderX, y(0.4), 0.03) },
    { bone: upperArmR, core: false, start: point(-shoulderX, y(0.76)), end: point(-shoulderX, y(0.6)) },
    { bone: forearmR, core: false, start: point(-shoulderX, y(0.6)), end: point(-shoulderX, y(0.46)) },
    { bone: handR, core: false, start: point(-shoulderX, y(0.46)), end: point(-shoulderX, y(0.4), 0.03) },
    { bone: upperLegL, core: false, start: point(hipX, y(0.51)), end: point(hipX, y(0.27)) },
    { bone: lowerLegL, core: false, start: point(hipX, y(0.27)), end: point(hipX, y(0.045)) },
    { bone: footL, core: false, start: point(hipX, y(0.045)), end: point(hipX, y(0), 0.06) },
    { bone: upperLegR, core: false, start: point(-hipX, y(0.51)), end: point(-hipX, y(0.27)) },
    { bone: lowerLegR, core: false, start: point(-hipX, y(0.27)), end: point(-hipX, y(0.045)) },
    { bone: footR, core: false, start: point(-hipX, y(0.045)), end: point(-hipX, y(0), 0.06) },
  ]
  const bones = [
    hips, spine, chest, neck, head,
    shoulderL, upperArmL, forearmL, handL,
    shoulderR, upperArmR, forearmR, handR,
    upperLegL, lowerLegL, footL,
    upperLegR, lowerLegR, footR,
  ]
  skinToBones(geometry, bones, segments)
  const mesh = new THREE.SkinnedMesh(geometry, mannequin)
  mesh.add(hips)
  mesh.updateMatrixWorld(true)
  mesh.bind(new THREE.Skeleton(bones), mesh.matrixWorld)
  mesh.normalizeSkinWeights()
  mesh.frustumCulled = false
  mesh.castShadow = true
  mesh.receiveShadow = true
  return { mesh, spine, neck, upperArmL, forearmL, upperArmR, forearmR, lowerLegL, lowerLegR }
}

function degrees(name) {
  const input = document.querySelector(`[data-pose="${name}"]`)
  return ((Number(input?.value) || 0) * Math.PI) / 180
}

function shapeNumber(name) {
  return Number(document.querySelector(`[data-shape="${name}"]`)?.value) || 0
}

function shapeDegrees(name) {
  return (shapeNumber(name) * Math.PI) / 180
}

const shapeMorphs = [
  'chest', 'chestDepth', 'shoulders', 'shoulderThick', 'bust', 'waist', 'stomach',
  'hips', 'hipLow', 'hipHeight', 'seat', 'seatLength', 'seatDepth',
  'thighUpper', 'thighLower', 'muscle', 'fat',
  'armLength', 'biceps', 'forearm', 'hands', 'legLength', 'calves', 'feet',
]

function buildLabel(value) {
  if (value <= -60) return 'Thin'
  if (value < -15) return 'Thin–average'
  if (value <= 15) return 'Average'
  if (value < 60) return 'Average–heavy'
  return 'Heavy'
}

function writeShapeReadout() {
  document.querySelectorAll('[data-readout]').forEach((node) => {
    const name = node.dataset.readout
    const value = shapeNumber(name)
    if (name === 'height') node.textContent = `${Math.round(value)} cm`
    else if (name === 'build') node.textContent = buildLabel(value)
    else if (name === 'shine') node.textContent = `${Math.round(value)}`
    else node.textContent = `${value > 0 ? '+' : ''}${value}`
  })
}

function writeFit() {
  const fit = document.getElementById('fit')
  if (!fit) return
  if (buildBase === 'female' || buildBase === 'male') {
    const sex = buildBase === 'male' ? 'Male' : 'Female'
    fit.textContent = `${sex}, ${buildLabel(shapeNumber('build'))}. The other sliders still change this body.`
    return
  }
  fit.textContent = 'Open Avatar to choose a gender and add photos. Build still changes this body.'
}

function resetShapeSliders() {
  const heightSlider = document.querySelector('[data-shape="height"]')
  if (heightSlider) heightSlider.value = String(Math.round(restHeight * 100))
  const shine = document.querySelector('[data-shape="shine"]')
  if (shine) shine.value = '20'
  for (const name of [...shapeMorphs, 'build', 'shoulderSlope', 'pelvisTilt']) {
    const slider = document.querySelector(`[data-shape="${name}"]`)
    if (slider) slider.value = '0'
  }
}

function boneWeights(mesh, names) {
  const position = mesh.geometry.attributes.position
  const mask = new Float32Array(position.count)
  const skinIndex = mesh.geometry.attributes.skinIndex
  const skinWeight = mesh.geometry.attributes.skinWeight
  if (!skinIndex || !skinWeight || !mesh.skeleton) return mask
  const selected = new Set()
  mesh.skeleton.bones.forEach((bone, index) => {
    if (names.some((name) => bone.name === name || bone.name.includes(name))) selected.add(index)
  })
  for (let index = 0; index < position.count; index += 1) {
    let sum = 0
    for (let channel = 0; channel < 4; channel += 1) {
      if (selected.has(skinIndex.getComponent(index, channel))) sum += skinWeight.getComponent(index, channel)
    }
    mask[index] = sum
  }
  return mask
}

function bonePoint(mesh, name) {
  const bone = mesh.skeleton?.bones?.find((item) => item.name === name)
  const point = new THREE.Vector3()
  if (!bone) return point
  bone.getWorldPosition(point)
  mesh.worldToLocal(point)
  return point
}

function addShapeMorphs(mesh) {
  const geometry = mesh.geometry
  const position = geometry.attributes.position
  const normal = geometry.attributes.normal
  if (!position || !normal) return
  mesh.updateMatrixWorld(true)
  const channels = Object.fromEntries(shapeMorphs.map((name) => [name, new Float32Array(position.count * 3)]))
  let minY = Infinity
  let maxY = -Infinity
  for (let index = 0; index < position.count; index += 1) {
    const y = position.getY(index)
    if (y < minY) minY = y
    if (y > maxY) maxY = y
  }
  const height = Math.max(maxY - minY, 1e-4)
  const hipY = minY + height * 0.52
  const shoulderWeight = boneWeights(mesh, ['left_shoulder', 'right_shoulder'])
  const elbowWeight = boneWeights(mesh, ['left_elbow', 'right_elbow'])
  const handWeight = boneWeights(mesh, ['wrist', 'thumb', 'index', 'middle', 'ring', 'pinky'])
  const hipWeight = boneWeights(mesh, ['left_hip', 'right_hip'])
  const kneeWeight = boneWeights(mesh, ['left_knee', 'right_knee'])
  const ankleWeight = boneWeights(mesh, ['left_ankle', 'right_ankle'])
  const footWeight = boneWeights(mesh, ['left_foot', 'right_foot'])
  const leftWrist = bonePoint(mesh, 'left_wrist')
  const rightWrist = bonePoint(mesh, 'right_wrist')
  const leftAnkle = bonePoint(mesh, 'left_ankle')
  const rightAnkle = bonePoint(mesh, 'right_ankle')
  for (let index = 0; index < position.count; index += 1) {
    const x = position.getX(index)
    const y = position.getY(index)
    const z = position.getZ(index)
    const yn = (y - minY) / height
    const nx = normal.getX(index)
    const ny = normal.getY(index)
    const nz = normal.getZ(index)
    const outward = Math.abs(ny) < 0.65
    const chestBand = Math.exp(-(((yn - 0.71) / 0.05) ** 2))
    const torso = Math.abs(x) < height * 0.16
    channels.chest[index * 3] = nx * 0.1 * chestBand * (torso ? 1 : 0)
    channels.chestDepth[index * 3 + 2] = nz * 0.08 * chestBand * (torso ? 1 : 0)
    const shoulderBand = Math.exp(-(((yn - 0.8) / 0.04) ** 2))
    const onShoulder = Math.abs(x) > height * 0.08 && Math.abs(x) < height * 0.26 && yn > 0.72 && yn < 0.88
    channels.shoulders[index * 3] = Math.sign(x) * 0.14 * shoulderBand * (onShoulder ? 1 : 0)
    channels.shoulderThick[index * 3] = nx * 0.04 * shoulderBand * (onShoulder ? 1 : 0)
    channels.shoulderThick[index * 3 + 2] = nz * 0.04 * shoulderBand * (onShoulder ? 1 : 0)
    const bustBand = Math.exp(-(((yn - 0.7) / 0.035) ** 2))
    const front = z > 0.01 && nz > 0.15 && Math.abs(x) > height * 0.02 && Math.abs(x) < height * 0.13
    channels.bust[index * 3] = nx * 0.045 * bustBand * (front ? 1 : 0)
    channels.bust[index * 3 + 2] = 0.1 * bustBand * (front ? 1 : 0)
    const waistBand = Math.exp(-(((yn - 0.6) / 0.04) ** 2))
    const waistTorso = Math.abs(x) < height * 0.15 && yn > 0.52 && yn < 0.68
    channels.waist[index * 3] = nx * 0.09 * waistBand * (waistTorso ? 1 : 0)
    channels.waist[index * 3 + 2] = nz * 0.09 * waistBand * (waistTorso ? 1 : 0)
    const stomachBand = Math.exp(-(((yn - 0.58) / 0.035) ** 2))
    const stomach = z > 0.005 && nz > 0 && Math.abs(x) < height * 0.12 && Math.abs(ny) < 0.75
    channels.stomach[index * 3] = nx * 0.025 * stomachBand * (stomach ? 1 : 0)
    channels.stomach[index * 3 + 2] = 0.1 * stomachBand * (stomach ? 1 : 0)
    const hipBand = Math.exp(-(((yn - 0.53) / 0.03) ** 2))
    const hipSide = Math.abs(x) > height * 0.07 && Math.abs(x) < height * 0.16 && yn > 0.48 && yn < 0.58
    channels.hips[index * 3] = Math.sign(x) * 0.05 * hipBand * (hipSide ? 1 : 0)
    const lowBand = Math.exp(-(((yn - 0.45) / 0.028) ** 2))
    const hipLow = Math.abs(x) > height * 0.07 && Math.abs(x) < height * 0.15 && yn > 0.4 && yn < 0.49
    channels.hipLow[index * 3] = Math.sign(x) * 0.045 * lowBand * (hipLow ? 1 : 0)
    const hipCenter = minY + height * 0.5
    channels.hipHeight[index * 3 + 1] = hipSide ? (y - hipCenter) * 0.45 * hipBand : 0
    const seatBand = Math.exp(-(((yn - 0.47) / 0.03) ** 2))
    const seat = z < -0.01 && Math.abs(x) > height * 0.04 && Math.abs(x) < height * 0.13 && yn > 0.4 && yn < 0.54
    channels.seat[index * 3] = Math.sign(x) * 0.045 * seatBand * (seat ? 1 : 0)
    const seatCenter = minY + height * 0.47
    channels.seatLength[index * 3 + 1] = seat ? (y - seatCenter) * 0.5 * seatBand : 0
    channels.seatDepth[index * 3 + 2] = seat ? -0.055 * seatBand : 0
    const upperThigh = hipWeight[index] > 0.2 && Math.abs(x) > height * 0.05 && Math.abs(x) < height * 0.16 && yn > 0.34 && yn < 0.5
    channels.thighUpper[index * 3] = nx * 0.04 * (upperThigh ? 1 : 0)
    channels.thighUpper[index * 3 + 2] = nz * 0.04 * (upperThigh ? 1 : 0)
    const lowerThigh = kneeWeight[index] > 0.2 && Math.abs(x) > height * 0.04 && Math.abs(x) < height * 0.14 && yn > 0.24 && yn < 0.38
    channels.thighLower[index * 3] = nx * 0.035 * (lowerThigh ? 1 : 0)
    channels.thighLower[index * 3 + 2] = nz * 0.035 * (lowerThigh ? 1 : 0)
    const shoulderCap = Math.exp(-(((yn - 0.8) / 0.03) ** 2)) * (Math.abs(x) > height * 0.1 && Math.abs(x) < height * 0.22 ? 1 : 0)
    const armBelly = shoulderWeight[index] > 0.25 && Math.abs(x) > height * 0.18 ? 0.7 : 0
    const chestCap = Math.exp(-(((yn - 0.72) / 0.035) ** 2)) * (torso ? 1 : 0)
    const thighCap = upperThigh ? 0.8 : 0
    const muscle = outward ? 0.04 * shoulderCap + 0.035 * armBelly + 0.03 * chestCap + 0.035 * thighCap : 0
    channels.muscle[index * 3] = nx * muscle
    channels.muscle[index * 3 + 2] = nz * muscle
    const belly = Math.exp(-(((yn - 0.58) / 0.04) ** 2)) * (Math.abs(x) < height * 0.13 ? 1 : 0)
    const hipSoft = Math.exp(-(((yn - 0.48) / 0.035) ** 2)) * (Math.abs(x) < height * 0.16 ? 1 : 0)
    const fat = outward ? 0.055 * belly + 0.04 * hipSoft + 0.03 * (upperThigh ? 1 : 0) : 0
    channels.fat[index * 3] = nx * fat
    channels.fat[index * 3 + 2] = nz * fat * (belly > 0.2 ? 1.4 : 1)
    const armReach = Math.abs(x) > height * 0.16 ? shoulderWeight[index] * 0.45 + elbowWeight[index] + handWeight[index] : 0
    channels.armLength[index * 3] = Math.sign(x) * 0.06 * Math.min(armReach, 1)
    const bicep = shoulderWeight[index] > 0.25 && Math.abs(x) > height * 0.18 && Math.abs(ny) < 0.7
    channels.biceps[index * 3] = nx * 0.035 * (bicep ? 1 : 0)
    channels.biceps[index * 3 + 2] = nz * 0.035 * (bicep ? 1 : 0)
    const forearm = elbowWeight[index] > 0.3 && Math.abs(x) > height * 0.28 && Math.abs(ny) < 0.75
    channels.forearm[index * 3] = nx * 0.03 * (forearm ? 1 : 0)
    channels.forearm[index * 3 + 2] = nz * 0.03 * (forearm ? 1 : 0)
    if (handWeight[index] > 0.35) {
      const wrist = x > 0 ? leftWrist : rightWrist
      channels.hands[index * 3] = (x - wrist.x) * 0.4 * handWeight[index]
      channels.hands[index * 3 + 1] = (y - wrist.y) * 0.4 * handWeight[index]
      channels.hands[index * 3 + 2] = (z - wrist.z) * 0.4 * handWeight[index]
    }
    const leg = y < hipY && Math.abs(x) < height * 0.2 ? 1 : 0
    channels.legLength[index * 3 + 1] = leg ? (y - hipY) * 0.12 : 0
    const calf = ankleWeight[index] > 0.25 && yn > 0.06 && yn < 0.24 && Math.abs(x) < height * 0.12
    channels.calves[index * 3] = nx * 0.035 * (calf ? 1 : 0)
    channels.calves[index * 3 + 2] = nz * 0.035 * (calf ? 1 : 0)
    if (footWeight[index] > 0.2 && yn < 0.1) {
      const ankle = x > 0 ? leftAnkle : rightAnkle
      channels.feet[index * 3] = (x - ankle.x) * 0.28 * footWeight[index]
      channels.feet[index * 3 + 1] = (y - minY) * 0.22 * footWeight[index]
      channels.feet[index * 3 + 2] = (z - ankle.z) * 0.28 * footWeight[index]
    }
  }
  geometry.morphAttributes.position = shapeMorphs.map((name) => new THREE.BufferAttribute(channels[name], 3))
  geometry.morphTargetsRelative = true
  const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
  materials.forEach((material) => {
    material.morphTargets = true
    material.needsUpdate = true
  })
  mesh.morphTargetInfluences = shapeMorphs.map(() => 0)
  mesh.updateMorphTargets()
}

function paintColors(mesh = rig?.mesh) {
  if (!mesh?.geometry?.attributes?.position) return
  const skin = new THREE.Color(skinColors[skinChoice] || skinColors.light)
  const hair = new THREE.Color(hairColors[hairChoice] || hairColors.brown)
  const iris = new THREE.Color(eyeColors[eyeChoice] || eyeColors.hazel)
  const sclera = new THREE.Color('#f3f0ea')
  const pupil = new THREE.Color('#14110e')
  const position = mesh.geometry.attributes.position
  const point = new THREE.Vector3()
  let crown = null
  let minY = Infinity
  for (let index = 0; index < position.count; index += 1) {
    point.fromBufferAttribute(position, index)
    if (point.y < minY) minY = point.y
    if (!crown || point.y > crown.y) crown = point.clone()
  }
  const span = Math.max((crown?.y || 0) - minY, 1e-4)
  const eyeBones = new Map()
  mesh.skeleton?.bones?.forEach((bone, index) => {
    if (bone.name.includes('eye')) eyeBones.set(index, bone.name)
  })
  const skinIndex = mesh.geometry.attributes.skinIndex
  const skinWeight = mesh.geometry.attributes.skinWeight
  const eyeCenters = new Map()
  if (skinIndex && skinWeight) {
    eyeBones.forEach((name, boneIndex) => {
      const center = new THREE.Vector3()
      let count = 0
      for (let index = 0; index < position.count; index += 1) {
        let weight = 0
        for (let channel = 0; channel < 4; channel += 1) {
          if (skinIndex.getComponent(index, channel) === boneIndex) weight += skinWeight.getComponent(index, channel)
        }
        if (weight < 0.4) continue
        point.fromBufferAttribute(position, index)
        center.add(point)
        count += 1
      }
      if (count) eyeCenters.set(boneIndex, center.multiplyScalar(1 / count))
    })
  }
  let colors = mesh.geometry.attributes.color
  if (!colors || colors.count !== position.count) {
    colors = new THREE.BufferAttribute(new Float32Array(position.count * 3), 3)
    mesh.geometry.setAttribute('color', colors)
  }
  for (let index = 0; index < position.count; index += 1) {
    point.fromBufferAttribute(position, index)
    let color = skin
    const onScalp = crown && (point.y - minY) / span > 0.945 && point.z < crown.z + 0.05
    if (onScalp) color = hair
    if (skinIndex && skinWeight) {
      eyeCenters.forEach((center, boneIndex) => {
        let weight = 0
        for (let channel = 0; channel < 4; channel += 1) {
          if (skinIndex.getComponent(index, channel) === boneIndex) weight += skinWeight.getComponent(index, channel)
        }
        if (weight < 0.4) return
        const offset = point.clone().sub(center)
        const spread = Math.hypot(offset.x, offset.y)
        if (offset.z > 0 && spread < 0.0045) color = pupil
        else if (offset.z > -0.002 && spread < 0.009) color = iris
        else color = sclera
      })
    }
    colors.setXYZ(index, color.r, color.g, color.b)
  }
  colors.needsUpdate = true
  const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
  materials.forEach((material) => {
    if (!material) return
    material.vertexColors = true
    material.color?.set(0xffffff)
    material.needsUpdate = true
  })
}

function applyShape() {
  writeShapeReadout()
  writeFit()
  if (!rig?.smplx) return
  const influences = rig.mesh.morphTargetInfluences
  if (influences && influences.length >= shapeMorphs.length) {
    shapeMorphs.forEach((name, index) => {
      influences[index] = shapeNumber(name) / 100
    })
    const build = shapeNumber('build') / 100
    if (influences.length >= shapeMorphs.length + 2) {
      influences[shapeMorphs.length] = build < 0 ? -build : 0
      influences[shapeMorphs.length + 1] = build > 0 ? build : 0
    }
  }
  const shine = shapeNumber('shine') / 100
  const materials = Array.isArray(rig.mesh.material) ? rig.mesh.material : [rig.mesh.material]
  materials.forEach((material) => {
    if (material && 'roughness' in material) material.roughness = 0.92 - shine * 0.67
  })
  const height = shapeNumber('height') / 100
  group.scale.setScalar(restHeight > 0 ? height / restHeight : 1)
  rig.root.position.y = 0
  rig.root.updateMatrixWorld(true)
  const box = new THREE.Box3().setFromObject(rig.mesh)
  rig.root.position.y = -box.min.y / (group.scale.y || 1)
}

function applyPose() {
  if (!rig) return
  if (rig.smplx) {
    const pose = rig.bones
    const slope = shapeDegrees('shoulderSlope')
    const tilt = shapeDegrees('pelvisTilt')
    pose.left_collar?.rotation.set(0, 0, 0)
    pose.right_collar?.rotation.set(0, 0, 0)
    pose.pelvis?.rotation.set(tilt, 0, 0)
    pose.left_shoulder?.rotation.set(0, degrees('armInL'), degrees('armL') + slope)
    pose.right_shoulder?.rotation.set(0, -degrees('armInR'), -(degrees('armR') + slope))
    pose.left_elbow?.rotation.set(degrees('elbowL'), 0, 0)
    pose.right_elbow?.rotation.set(degrees('elbowR'), 0, 0)
    pose.left_wrist?.rotation.set(degrees('wristL'), degrees('wristTwistL'), 0)
    pose.right_wrist?.rotation.set(degrees('wristR'), -degrees('wristTwistR'), 0)
    pose.left_hip?.rotation.set(degrees('legL') - tilt, 0, degrees('outL'))
    pose.right_hip?.rotation.set(degrees('legR') - tilt, 0, -degrees('outR'))
    pose.left_knee?.rotation.set(degrees('kneeL'), 0, 0)
    pose.right_knee?.rotation.set(degrees('kneeR'), 0, 0)
    pose.left_ankle?.rotation.set(degrees('ankleL'), 0, 0)
    pose.right_ankle?.rotation.set(degrees('ankleR'), 0, 0)
    pose.spine1?.rotation.set(degrees('spine') * 0.4, 0, 0)
    pose.spine2?.rotation.set(degrees('spine'), 0, 0)
    pose.spine3?.rotation.set(degrees('spine') * 0.45, 0, 0)
    pose.neck?.rotation.set(degrees('neck'), degrees('head') * 0.35, 0)
    pose.head?.rotation.set(0, degrees('head'), 0)
    pose.jaw?.rotation.set(degrees('jaw'), 0, 0)
    pose.left_eye_smplhf?.rotation.set(degrees('eyesUp'), degrees('eyes'), 0)
    pose.right_eye_smplhf?.rotation.set(degrees('eyesUp'), degrees('eyes'), 0)
    for (const side of ['left', 'right']) {
      const sign = side === 'left' ? 1 : -1
      for (const finger of ['index', 'middle', 'ring', 'pinky']) {
        const curl = degrees(`${side}${finger}`)
        for (let joint = 1; joint <= 3; joint += 1) pose[`${side}_${finger}${joint}`]?.rotation.set(curl, 0, 0)
      }
      const thumb = degrees(`${side}thumb`)
      pose[`${side}_thumb1`]?.rotation.set(0, thumb * sign, 0)
      pose[`${side}_thumb2`]?.rotation.set(thumb, 0, 0)
      pose[`${side}_thumb3`]?.rotation.set(thumb, 0, 0)
    }
  } else {
    rig.upperArmL.rotation.set(0, 0, Math.PI / 2 + degrees('armL'))
    rig.forearmL.rotation.set(degrees('elbowL'), 0, 0)
    rig.upperArmR.rotation.set(0, 0, -Math.PI / 2 - degrees('armR'))
    rig.forearmR.rotation.set(degrees('elbowR'), 0, 0)
    rig.lowerLegL.rotation.set(degrees('kneeL'), 0, 0)
    rig.lowerLegR.rotation.set(degrees('kneeR'), 0, 0)
    rig.spine.rotation.set(degrees('spine'), 0, 0)
    rig.neck.rotation.set(0, degrees('head'), 0)
  }
  applyShape()
}

function render() {
  resize()
  controls.update()
  if (rig?.root) rig.root.updateMatrixWorld(true)
  else if (rig?.mesh) rig.mesh.updateMatrixWorld(true)
  renderer.render(scene, camera)
}

async function showMesh(url, height, options = {}) {
  group.scale.set(1, 1, 1)
  if (!url) {
    render()
    return
  }
  if (url === shownUrl && rig) {
    applyPose()
    render()
    return
  }
  const token = ++loadToken
  shownUrl = url
  if (!options.keepBuild) buildBase = ''
  showError('')
  while (group.children.length) group.remove(group.children[0])
  rig = null
  skeletonHelper = null
  try {
    const gltf = await loader.loadAsync(url)
    if (token !== loadToken) return
    const object = gltf.scene
    let skinned = null
    object.traverse((child) => {
      if (child.isSkinnedMesh && !skinned) skinned = child
    })
    if (skinned?.skeleton?.bones?.some((bone) => bone.name === 'pelvis')) {
      const bones = {}
      skinned.skeleton.bones.forEach((bone) => {
        bones[bone.name] = bone
      })
      rig = { smplx: true, root: object, mesh: skinned, bones, restJoints: new Map() }
      object.position.set(0, 0, 0)
      group.add(object)
      for (const [name, bone] of Object.entries(bones)) {
        bone.scale.set(1, 1, 1)
        rig.restJoints.set(name, bone.position.clone())
      }
      addShapeMorphs(skinned)
      const materials = Array.isArray(skinned.material) ? skinned.material : [skinned.material]
      materials.forEach((material) => {
        if (material?.color) material.color.set(0xffffff)
        if (material && 'roughness' in material) material.roughness = 0.78
        if (material) material.vertexColors = true
      })
      paintColors(skinned)
      skeletonHelper = new THREE.SkeletonHelper(skinned)
      skeletonHelper.visible = document.getElementById('skeleton')?.checked !== false
      group.add(skeletonHelper)
      object.updateMatrixWorld(true)
      const box = new THREE.Box3().setFromObject(skinned)
      restHeight = Math.max(0.2, box.max.y - box.min.y)
      if (!options.keepShape) resetShapeSliders()
      applyPose()
      resetButton.hidden = false
      render()
      return
    }
    group.scale.set(1, height || 1, 1)
    fitStanding(object)
    object.updateMatrixWorld(true)
    const source = []
    object.traverse((child) => {
      if (child.isMesh) source.push(child)
    })
    if (!source.length) throw new Error('empty')
    source.sort((a, b) => b.geometry.attributes.position.count - a.geometry.attributes.position.count)
    const geometry = source[0].geometry.clone()
    geometry.applyMatrix4(source[0].matrixWorld)
    bodyMeasures = measureBody(geometry)
    bodySex = bodyMeasures.hint
    showBody()
  } catch (error) {
    console.error(error)
    if (token === loadToken) showError('This mesh could not be shown.')
  }
  render()
}

function onMessage(event) {
  let data = event.data
  if (typeof data === 'string') {
    try {
      data = JSON.parse(data)
    } catch {
      return
    }
  }
  if (!data || data.type !== 'scene') return
  showMesh(data.url || '', Number(data.height) || 1)
}

window.addEventListener('message', onMessage)
resetButton.addEventListener('click', () => {
  controls.reset()
  render()
})
document.querySelectorAll('[data-pose]').forEach((input) => {
  input.addEventListener('input', () => {
    if (!applyingPreset) {
      document.querySelectorAll('[data-preset]').forEach((button) => button.classList.remove('active'))
    }
    applyPose()
  })
})
document.querySelectorAll('[data-shape]').forEach((input) => {
  input.addEventListener('input', () => {
    if (input.dataset.shape === 'build') {
      startBuild()
      return
    }
    applyPose()
  })
})
document.querySelectorAll('[data-sex]').forEach((button) => {
  button.addEventListener('click', () => {
    photoSex = button.dataset.sex
    bodySex = button.dataset.sex
    document.querySelectorAll('[data-sex]').forEach((item) => item.classList.toggle('active', item === button))
    if (photoSex === 'female' || photoSex === 'male') {
      useBuild(photoSex)
      return
    }
    if (rig?.smplx) return
    showBody()
  })
})

function skinnedMeshOf(gltf) {
  let skinned = null
  gltf.scene.traverse((child) => {
    if (child.isSkinnedMesh && !skinned) skinned = child
  })
  return skinned
}

function startBuild() {
  if (photoSex !== 'female' && photoSex !== 'male') {
    photoSex = 'female'
    bodySex = 'female'
    document.querySelectorAll('[data-sex]').forEach((button) => button.classList.toggle('active', button.dataset.sex === 'female'))
  }
  const sex = photoSex === 'male' ? 'male' : 'female'
  const ready = buildBase === sex && shownUrl === `/presets/${sex}_average.glb` && (rig?.mesh?.morphTargetInfluences?.length || 0) >= shapeMorphs.length + 2
  if (ready) {
    applyPose()
    return
  }
  useBuild(sex)
}

async function attachBuildDeltas(sex, request) {
  const token = loadToken
  const [thinGltf, heavyGltf] = await Promise.all([
    loader.loadAsync(`/presets/${sex}_thin.glb`),
    loader.loadAsync(`/presets/${sex}_heavy.glb`),
  ])
  if (request !== buildRequest || token !== loadToken || buildBase !== sex || !rig?.mesh) return
  const base = rig.mesh.geometry.attributes.position
  const thin = skinnedMeshOf(thinGltf)?.geometry?.attributes?.position
  const heavy = skinnedMeshOf(heavyGltf)?.geometry?.attributes?.position
  if (!thin || !heavy || thin.count !== base.count || heavy.count !== base.count) return
  const thinDelta = new Float32Array(base.count * 3)
  const heavyDelta = new Float32Array(base.count * 3)
  for (let index = 0; index < base.count; index += 1) {
    thinDelta[index * 3] = thin.getX(index) - base.getX(index)
    thinDelta[index * 3 + 1] = thin.getY(index) - base.getY(index)
    thinDelta[index * 3 + 2] = thin.getZ(index) - base.getZ(index)
    heavyDelta[index * 3] = heavy.getX(index) - base.getX(index)
    heavyDelta[index * 3 + 1] = heavy.getY(index) - base.getY(index)
    heavyDelta[index * 3 + 2] = heavy.getZ(index) - base.getZ(index)
  }
  const attributes = rig.mesh.geometry.morphAttributes.position
  attributes.length = shapeMorphs.length
  attributes.push(new THREE.BufferAttribute(thinDelta, 3), new THREE.BufferAttribute(heavyDelta, 3))
  rig.mesh.geometry.morphTargetsRelative = true
  rig.mesh.updateMorphTargets()
  applyPose()
}

async function useBuild(sex) {
  const request = ++buildRequest
  buildBase = sex
  const url = `/presets/${sex}_average.glb`
  if (shownUrl !== url || !rig?.smplx) {
    await showMesh(url, 1, { keepShape: true, keepBuild: true })
  }
  if (request !== buildRequest) return
  await attachBuildDeltas(sex, request)
}
document.getElementById('reset-pose')?.addEventListener('click', () => {
  applyingPreset = true
  document.querySelectorAll('[data-pose]').forEach((input) => {
    input.value = '0'
  })
  document.querySelectorAll('[data-preset]').forEach((button) => button.classList.toggle('active', button.dataset.preset === 'tpose'))
  applyingPreset = false
  applyPose()
})
document.getElementById('reset-shape')?.addEventListener('click', () => {
  resetShapeSliders()
  applyPose()
})
document.getElementById('person-create')?.addEventListener('click', () => {
  createPerson().catch((error) => {
    console.error(error)
    showError(error instanceof Error ? error.message : 'The photo could not be turned into a body.')
    const button = document.getElementById('person-create')
    if (button) button.disabled = false
  })
})

const AVATAR_SERVICE = 'http://127.0.0.1:8766'

function renderPeople(people) {
  const root = document.getElementById('people')
  if (!root) return
  root.replaceChildren()
  for (const person of people) {
    const button = document.createElement('button')
    button.type = 'button'
    button.className = 'person'
    button.textContent = person.name
    button.addEventListener('click', () => {
      showMesh(person.url, 1)
    })
    root.append(button)
  }
}

async function loadPeople() {
  const people = [{ name: 'Current body', url: '/smplx_body.glb' }]
  try {
    const response = await fetch(`${AVATAR_SERVICE}/avatars`)
    if (response.ok) {
      const saved = await response.json()
      if (Array.isArray(saved)) people.push(...saved)
    }
  } catch {
    // The photo service is optional until a new person is created.
  }
  renderPeople(people)
}

const photoFiles = []

function renderPhotoList() {
  const root = document.getElementById('photo-list')
  if (!root) return
  root.replaceChildren()
  photoFiles.forEach((file, index) => {
    const row = document.createElement('div')
    row.className = 'photo-row'
    const name = document.createElement('span')
    name.textContent = file.name
    const remove = document.createElement('button')
    remove.type = 'button'
    remove.textContent = 'Remove'
    remove.addEventListener('click', () => {
      photoFiles.splice(index, 1)
      renderPhotoList()
    })
    row.append(name, remove)
    root.append(row)
  })
}

async function usePrototype(url, label) {
  const response = await fetch(url)
  if (!response.ok) throw new Error('The prototype photo could not be loaded.')
  const blob = await response.blob()
  photoFiles.push(new File([blob], label, { type: blob.type || 'image/jpeg' }))
  renderPhotoList()
  showPanel('photo-panel')
}

document.getElementById('proto-female')?.addEventListener('click', () => {
  usePrototype('/prototypes/female.jpg', 'female-prototype.jpg').catch((error) => showError(error.message))
})
document.getElementById('proto-male')?.addEventListener('click', () => {
  usePrototype('/prototypes/male.jpg', 'male-prototype.jpg').catch((error) => showError(error.message))
})

document.getElementById('photo-add')?.addEventListener('change', (event) => {
  for (const file of event.target.files || []) photoFiles.push(file)
  event.target.value = ''
  renderPhotoList()
})

async function createPerson() {
  const name = document.getElementById('person-name')?.value?.trim() || 'Person'
  const button = document.getElementById('person-create')
  if (!photoFiles.length) {
    showError('Add at least one full-body photo. A front T-pose is the one that sets the body.')
    return
  }
  if (button) button.disabled = true
  showError('')
  const fit = document.getElementById('fit')
  const cleared = await fetch(`${AVATAR_SERVICE}/avatar-clear?name=${encodeURIComponent(name)}`, { method: 'POST' })
  if (!cleared.ok) throw new Error('The photo list could not be started.')
  for (let index = 0; index < photoFiles.length; index += 1) {
    if (fit) fit.textContent = `Sending photo ${index + 1} of ${photoFiles.length}.`
    const saved = await fetch(
      `${AVATAR_SERVICE}/avatar-photo?name=${encodeURIComponent(name)}&slot=p${index}`,
      { method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: photoFiles[index] },
    )
    if (!saved.ok) {
      const detail = (await saved.text()).trim()
      throw new Error(detail || `Photo service returned ${saved.status}`)
    }
  }
  if (fit) fit.textContent = `Sorting the views and building ${name}. Each photo takes a minute or two.`
  const gender = photoSex === 'auto' ? 'auto' : photoSex
  const response = await fetch(
    `${AVATAR_SERVICE}/avatar-build?name=${encodeURIComponent(name)}&gender=${encodeURIComponent(gender)}`,
    { method: 'POST' },
  )
  if (!response.ok) {
    const detail = (await response.text()).trim()
    throw new Error(detail || `Photo service returned ${response.status}`)
  }
  const savedUrl = response.headers.get('X-Avatar-Url')
  const detected = response.headers.get('X-Avatar-Gender') || 'neutral'
  const views = response.headers.get('X-Avatar-Views') || ''
  const hair = response.headers.get('X-Avatar-Hair')
  if (hair) {
    const sampled = new THREE.Color(`#${hair.replace('#', '')}`)
    let nearest = 'brown'
    let score = Infinity
    Object.entries(hairColors).forEach(([name, value]) => {
      const preset = new THREE.Color(value)
      const distance = (sampled.r - preset.r) ** 2 + (sampled.g - preset.g) ** 2 + (sampled.b - preset.b) ** 2
      if (distance < score) {
        score = distance
        nearest = name
      }
    })
    hairChoice = nearest
    document.querySelectorAll('[data-hair]').forEach((button) => button.classList.toggle('active', button.dataset.hair === nearest))
  }
  const blobUrl = URL.createObjectURL(await response.blob())
  await showMesh(blobUrl, 1)
  paintColors()
  if (button) button.disabled = false
  if (savedUrl) await loadPeople()
  const summary = views ? views.replaceAll(',', ', ') : `${photoFiles.length} photos`
  if (fit) fit.textContent = `${name} is ready. Detected ${detected}. Views: ${summary}.`
}

document.querySelectorAll('[data-skin]').forEach((button) => {
  button.addEventListener('click', () => {
    skinChoice = button.dataset.skin
    document.querySelectorAll('[data-skin]').forEach((item) => item.classList.toggle('active', item === button))
    paintColors()
    render()
  })
})
document.querySelectorAll('[data-hair]').forEach((button) => {
  button.addEventListener('click', () => {
    hairChoice = button.dataset.hair
    document.querySelectorAll('[data-hair]').forEach((item) => item.classList.toggle('active', item === button))
    paintColors()
    render()
  })
})
document.querySelectorAll('[data-eye]').forEach((button) => {
  button.addEventListener('click', () => {
    eyeChoice = button.dataset.eye
    document.querySelectorAll('[data-eye]').forEach((item) => item.classList.toggle('active', item === button))
    paintColors()
    render()
  })
})
document.querySelectorAll('[data-preset]').forEach((button) => {
  button.addEventListener('click', () => {
    const preset = posePresets[button.dataset.preset] || {}
    applyingPreset = true
    document.querySelectorAll('[data-pose]').forEach((input) => {
      input.value = '0'
    })
    Object.entries(preset).forEach(([name, value]) => {
      const input = document.querySelector(`[data-pose="${name}"]`)
      if (input) input.value = String(value)
    })
    document.querySelectorAll('[data-preset]').forEach((item) => item.classList.toggle('active', item === button))
    applyingPreset = false
    applyPose()
    render()
  })
})
function showPanel(id) {
  if (id === 'move-panel') return
  const panel = document.getElementById(id)
  const sheet = document.querySelector('.sheet')
  const opening = Boolean(panel?.hidden)
  document.querySelectorAll('.panel').forEach((item) => {
    item.hidden = true
  })
  document.querySelectorAll('[data-panel]').forEach((item) => item.classList.remove('active'))
  if (opening && panel) {
    panel.hidden = false
    document.querySelector(`[data-panel="${id}"]`)?.classList.add('active')
    if (sheet) sheet.hidden = false
  } else if (sheet) sheet.hidden = true
  resize()
}

document.querySelectorAll('[data-panel]').forEach((button) => {
  button.addEventListener('click', () => showPanel(button.dataset.panel))
})

const raycaster = new THREE.Raycaster()
const pointer = new THREE.Vector2()
let limbDrag = null

function poseKeyForBone(name) {
  const left = name.startsWith('left')
  const side = left ? 'left' : 'right'
  if (name.includes('thumb')) return `${side}thumb`
  if (name.includes('index')) return `${side}index`
  if (name.includes('middle')) return `${side}middle`
  if (name.includes('ring')) return `${side}ring`
  if (name.includes('pinky')) return `${side}pinky`
  if (name.includes('shoulder') || name.includes('collar')) return left ? 'armL' : 'armR'
  if (name.includes('elbow')) return left ? 'elbowL' : 'elbowR'
  if (name.includes('wrist')) return left ? 'wristL' : 'wristR'
  if (name.includes('hip')) return left ? 'legL' : 'legR'
  if (name.includes('knee')) return left ? 'kneeL' : 'kneeR'
  if (name.includes('ankle') || name.includes('foot')) return left ? 'ankleL' : 'ankleR'
  if (name.includes('jaw')) return 'jaw'
  if (name.includes('eye')) return 'eyes'
  if (name === 'head') return 'head'
  if (name.includes('neck')) return 'neck'
  if (name.includes('spine')) return 'spine'
  return null
}

function boneUnderPointer(event) {
  if (!rig?.mesh) return null
  const rect = canvas.getBoundingClientRect()
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
  raycaster.setFromCamera(pointer, camera)
  const hits = raycaster.intersectObject(rig.mesh, false)
  const hit = hits[0]
  const skinIndex = rig.mesh.geometry.attributes.skinIndex
  const skinWeight = rig.mesh.geometry.attributes.skinWeight
  if (!hit?.face || !skinIndex || !skinWeight) return null
  const vertex = hit.face.a
  let best = 0
  let weight = -1
  for (let channel = 0; channel < 4; channel += 1) {
    const value = skinWeight.getComponent(vertex, channel)
    if (value > weight) {
      weight = value
      best = skinIndex.getComponent(vertex, channel)
    }
  }
  return rig.mesh.skeleton.bones[best]?.name || null
}

canvas.addEventListener('pointerdown', (event) => {
  if (event.button != null && event.button !== 0) return
  const key = poseKeyForBone(boneUnderPointer(event) || '')
  const input = key ? document.querySelector(`[data-pose="${key}"]`) : null
  if (!input) return
  limbDrag = { id: event.pointerId, x: event.clientX, y: event.clientY, input, sideways: key === 'head' || key === 'eyes' }
  controls.enabled = false
  canvas.setPointerCapture(event.pointerId)
})
canvas.addEventListener('pointermove', (event) => {
  if (!limbDrag || event.pointerId !== limbDrag.id) return
  const delta = limbDrag.sideways ? event.clientX - limbDrag.x : limbDrag.y - event.clientY
  limbDrag.x = event.clientX
  limbDrag.y = event.clientY
  const min = Number(limbDrag.input.min)
  const max = Number(limbDrag.input.max)
  const next = Math.min(max, Math.max(min, Number(limbDrag.input.value) + delta * 0.45))
  limbDrag.input.value = String(Math.round(next))
  limbDrag.input.dispatchEvent(new Event('input', { bubbles: true }))
})
function endLimbDrag(event) {
  if (!limbDrag || event.pointerId !== limbDrag.id) return
  limbDrag = null
  controls.enabled = true
}
canvas.addEventListener('pointerup', endLimbDrag)
canvas.addEventListener('pointercancel', endLimbDrag)

document.getElementById('skeleton')?.addEventListener('change', (event) => {
  if (skeletonHelper) skeletonHelper.visible = event.target.checked
})
window.addEventListener('resize', render)
renderer.setAnimationLoop(render)
window.parent.postMessage(JSON.stringify({ type: 'ready' }), '*')
const preset = new URLSearchParams(location.search).get('mesh')
if (preset) showMesh(preset, 1)
loadPeople()
writeShapeReadout()
