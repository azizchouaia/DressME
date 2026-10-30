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
scene.add(new THREE.HemisphereLight(0xfff7ef, 0xe4d5c6, 1.25))
const key = new THREE.DirectionalLight(0xfffaf6, 1.7)
key.position.set(2.2, 4.2, 3.4)
scene.add(key)
const fill = new THREE.DirectionalLight(0xffe8d2, 0.55)
fill.position.set(-2.6, 2.2, 2.2)
scene.add(fill)

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
  black: '#2a1c16',
  brown: '#7a4a2a',
  red: '#c45a32',
  blonde: '#e8c56e',
}
const skinColors = {
  fair: '#ffd8c6',
  light: '#f3c2a4',
  warm: '#e8a56e',
  tan: '#c98456',
  brown: '#8d5a3c',
  deep: '#5c3828',
}
const eyeColors = {
  hazel: '#a67c3d',
  black: '#2a211c',
  green: '#4e8a58',
  blue: '#4c86b8',
}

const posePresets = {
  front: { armL: -68, armR: -68, elbowL: 22, elbowR: 22, armInL: 10, armInR: 10, outL: 7, outR: 7, wristL: 8, wristR: 8 },
  glance: { armL: -72, armR: -66, elbowL: 18, elbowR: 28, armInL: 6, armInR: 14, outL: 4, outR: 10, legL: 10, legR: -6, kneeR: 8, head: 32, neck: 8 },
  casual: { armL: -58, armR: -58, elbowL: 42, elbowR: 42, armInL: 18, armInR: 18, outL: 8, outR: 8, wristL: 6, wristR: 6 },
}

function resize() {
  const width = canvas.clientWidth || 1
  const height = canvas.clientHeight || 1
  const pixelWidth = Math.floor(width * renderer.getPixelRatio())
  const pixelHeight = Math.floor(height * renderer.getPixelRatio())
  if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) renderer.setSize(width, height, false)
  const blocks = [document.querySelector('.build-bar'), document.querySelector('.sheet')]
    .filter((node) => node && !node.hidden)
  let left = 0
  let right = width
  let top = 0
  let bottom = height
  blocks.forEach((node) => {
    const rect = node.getBoundingClientRect()
    const across = rect.left < width * 0.62 && rect.right > width * 0.38
    if (across && rect.top > height * 0.45) bottom = Math.min(bottom, rect.top)
    else if (rect.left > width * 0.45) right = Math.min(right, rect.left - 12)
  })
  const freeCenterX = left + Math.max(1, right - left) / 2
  const freeCenterY = top + Math.max(1, bottom - top) / 2
  camera.aspect = width / height
  camera.setViewOffset(width, height, width / 2 - freeCenterX, height / 2 - freeCenterY, width, height)
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
  if (shine) shine.value = '48'
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
  if (activeSock === 'thin') tintThinSocks(mesh, colors)
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
  fitAccessories()
  fitFootwear()
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
    pose.left_elbow?.rotation.set(0, -degrees('elbowL'), 0)
    pose.right_elbow?.rotation.set(0, degrees('elbowR'), 0)
    pose.left_wrist?.rotation.set(degrees('wristL'), degrees('wristTwistL'), 0)
    pose.right_wrist?.rotation.set(degrees('wristR'), -degrees('wristTwistR'), 0)
    pose.left_hip?.rotation.set(degrees('legL') - tilt, 0, degrees('outL'))
    pose.right_hip?.rotation.set(degrees('legR') - tilt, 0, -degrees('outR'))
    pose.left_knee?.rotation.set(degrees('kneeL'), 0, 0)
    pose.right_knee?.rotation.set(degrees('kneeR'), 0, 0)
    const planted = activeShoe ? (footPreset[activeShoe] * Math.PI) / 180 : null
    if (activeShoe) {
      for (const name of ['ankleL', 'ankleR']) {
        const input = document.querySelector(`[data-pose="${name}"]`)
        if (input) input.value = String(footPreset[activeShoe])
      }
    }
    pose.left_ankle?.rotation.set(planted ?? degrees('ankleL'), 0, 0)
    pose.right_ankle?.rotation.set(planted ?? degrees('ankleR'), 0, 0)
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
    rig.forearmL.rotation.set(0, -degrees('elbowL'), 0)
    rig.upperArmR.rotation.set(0, 0, -Math.PI / 2 - degrees('armR'))
    rig.forearmR.rotation.set(0, degrees('elbowR'), 0)
    rig.lowerLegL.rotation.set(degrees('kneeL'), 0, 0)
    rig.lowerLegR.rotation.set(degrees('kneeR'), 0, 0)
    rig.spine.rotation.set(degrees('spine'), 0, 0)
    rig.neck.rotation.set(0, degrees('head'), 0)
  }
  applyShape()
}

const clothSkin = new THREE.Vector3()
let clothTimer = 0
let clothBuilder = 'sith'

function garmentMeshes() {
  const meshes = []
  group.traverse((child) => {
    if (child.isSkinnedMesh && child.userData.garment) meshes.push(child)
  })
  return meshes
}

function stepCloth(dt) {
  const damp = Math.pow(0.84, dt * 60)
  const spring = 1 - Math.pow(0.78, dt * 60)
  let energy = 0
  for (const mesh of garmentMeshes()) {
    if (mesh.userData.rigid) continue
    const bind = mesh.userData.bindPos
    const shown = mesh.userData.clothPos
    const vel = mesh.userData.clothVel
    const pos = mesh.geometry.attributes.position
    if (!bind || !shown || !vel) continue
    let minY = Infinity
    let maxY = -Infinity
    for (let index = 1; index < bind.length; index += 3) {
      minY = Math.min(minY, bind[index])
      maxY = Math.max(maxY, bind[index])
    }
    const span = Math.max(maxY - minY, 1e-4)
    pos.array.set(bind)
    mesh.material.skinning = true
    mesh.skeleton.update()
    for (let index = 0; index < pos.count; index += 1) {
      mesh.boneTransform(index, clothSkin)
      const offset = index * 3
      const hem = 1 - (bind[offset + 1] - minY) / span
      const follow = spring * (0.35 + 0.65 * (1 - hem))
      const drag = damp * (0.9 + 0.1 * hem)
      vel[offset] = vel[offset] * drag + (clothSkin.x - shown[offset]) * follow
      vel[offset + 1] = vel[offset + 1] * drag + (clothSkin.y - shown[offset + 1]) * follow - hem * 0.00035
      vel[offset + 2] = vel[offset + 2] * drag + (clothSkin.z - shown[offset + 2]) * follow
      shown[offset] += vel[offset]
      shown[offset + 1] += vel[offset + 1]
      shown[offset + 2] += vel[offset + 2]
      energy += vel[offset] * vel[offset] + vel[offset + 1] * vel[offset + 1] + vel[offset + 2] * vel[offset + 2]
    }
    pos.array.set(shown)
    pos.needsUpdate = true
    mesh.material.skinning = false
  }
  return energy
}

function settleCloth() {
  if (clothTimer) cancelAnimationFrame(clothTimer)
  let last = performance.now()
  const tick = (now) => {
    const dt = Math.min(0.05, (now - last) / 1000)
    last = now
    const energy = stepCloth(dt)
    render()
    clothTimer = energy > 0.0008 ? requestAnimationFrame(tick) : 0
  }
  clothTimer = requestAnimationFrame(tick)
}

function render() {
  resize()
  controls.update()
  if (rig?.root) rig.root.updateMatrixWorld(true)
  else if (rig?.mesh) rig.mesh.updateMatrixWorld(true)
  renderer.render(scene, camera)
}

const garmentFiles = [
  ['/garments/shirt.glb', 0xc5c8cc, ''],
  ['/garments/shorts.glb', 0x2c3140, ''],
  ['/garments/vest.glb', 0x1a1c22, ''],
  ['/garments/hat.glb', 0x1a1a1a, 'hat'],
  ['/garments/shoes.glb', 0xf3f0ea, 'shoes'],
  ['/garments/bag.glb', 0xc4a574, 'bag'],
]
const worn = { hat: true, shoes: false, bag: false }
let activeShoe = null
let activeSock = null
const footPreset = { flat: 0, sneaker: 12, heel: 32 }
const shoeMeshes = {}
let thickSock = null
const accessories = []
const springBones = []
let springTimer = 0

function jointRest(name) {
  const bones = rig?.mesh?.skeleton?.bones
  if (!bones) return null
  const index = bones.findIndex((bone) => bone.name === name)
  if (index < 0) return null
  return new THREE.Vector3().setFromMatrixPosition(new THREE.Matrix4().copy(rig.mesh.skeleton.boneInverses[index]).invert())
}

function morphedAt(index, target) {
  const position = rig.mesh.geometry.attributes.position
  target.fromBufferAttribute(position, index)
  const morphs = rig.mesh.geometry.morphAttributes.position || []
  const influences = rig.mesh.morphTargetInfluences || []
  for (let morph = 0; morph < morphs.length; morph += 1) {
    const weight = influences[morph] || 0
    if (!weight) continue
    target.x += morphs[morph].getX(index) * weight
    target.y += morphs[morph].getY(index) * weight
    target.z += morphs[morph].getZ(index) * weight
  }
  return target
}

function vertexNear(target) {
  const position = rig.mesh.geometry.attributes.position
  const point = new THREE.Vector3()
  let best = 0
  let bestDistance = Infinity
  for (let index = 0; index < position.count; index += 1) {
    point.fromBufferAttribute(position, index)
    const distance = point.distanceToSquared(target)
    if (distance < bestDistance) {
      bestDistance = distance
      best = index
    }
  }
  return best
}

function earVertex(sign) {
  const head = jointRest('head')
  const position = rig.mesh.geometry.attributes.position
  const point = new THREE.Vector3()
  let best = 0
  let bestSide = sign > 0 ? -Infinity : Infinity
  for (let index = 0; index < position.count; index += 1) {
    point.fromBufferAttribute(position, index)
    if (Math.abs(point.y - (head.y + 0.02)) > 0.04) continue
    if (Math.abs(point.z - head.z) > 0.035) continue
    const farther = sign > 0 ? point.x > bestSide : point.x < bestSide
    if (farther) {
      bestSide = point.x
      best = index
    }
  }
  return best
}

function trackAccessory(object, name, anchor, boneName, extra = new THREE.Vector3()) {
  object.userData.extra = name
  object.userData.anchor = anchor
  object.userData.boneName = boneName
  object.userData.extraOffset = extra
  object.visible = false
  object.traverse((child) => {
    child.frustumCulled = false
    child.castShadow = true
  })
  accessories.push(object)
  return object
}

let footwearCache = null
let restFoot = null
let knitMap = null
let knitNormal = null

function footIndices(side) {
  ensureFootwearCache()
  return footwearCache[side]
}

function sockIndices(side) {
  ensureFootwearCache()
  return side ? footwearCache.sock[side] : footwearCache.sock.all
}

function ensureFootwearCache() {
  if (footwearCache?.mesh === rig.mesh) return
  const mesh = rig.mesh
  const position = mesh.geometry.attributes.position
  footwearCache = { mesh, left: [], right: [], sock: { left: [], right: [], all: [] } }
  for (const side of ['left', 'right']) {
    const ankleWeight = boneWeights(mesh, [`${side}_ankle`])
    const footWeight = boneWeights(mesh, [`${side}_foot`])
    const kneeWeight = boneWeights(mesh, [`${side}_knee`])
    const ankle = jointRest(`${side}_ankle`)
    for (let index = 0; index < position.count; index += 1) {
      const y = position.getY(index)
      const footish = ankleWeight[index] + footWeight[index]
      if (footish > 0.5 && (!ankle || y <= ankle.y + 0.02)) footwearCache[side].push(index)
      if (footish > 0.18 || (kneeWeight[index] > 0.22 && ankle && y < ankle.y + 0.16)) {
        footwearCache.sock[side].push(index)
        footwearCache.sock.all.push(index)
      }
    }
  }
}

function toeBone(side) {
  const bones = rig.mesh.skeleton.bones
  for (const name of [`${side}_toe`, `${side}_toes`, `${side}_foot`]) {
    const index = bones.findIndex((bone) => bone.name === name)
    if (index >= 0) return index
  }
  return -1
}

function addBox(parts, min, max) {
  const size = max.clone().sub(min)
  if (size.x < 1e-4 || size.y < 1e-4 || size.z < 1e-4) return
  const geometry = new THREE.BoxGeometry(size.x, size.y, size.z)
  geometry.translate((min.x + max.x) / 2, (min.y + max.y) / 2, (min.z + max.z) / 2)
  parts.push(geometry)
}

function mergeParts(parts) {
  let count = 0
  let indexCount = 0
  for (const geometry of parts) {
    count += geometry.attributes.position.count
    indexCount += geometry.index.count
  }
  const position = new Float32Array(count * 3)
  const normal = new Float32Array(count * 3)
  const index = new Uint32Array(indexCount)
  let vertex = 0
  let offset = 0
  for (const geometry of parts) {
    position.set(geometry.attributes.position.array, vertex * 3)
    normal.set(geometry.attributes.normal.array, vertex * 3)
    const source = geometry.index.array
    for (let i = 0; i < source.length; i += 1) index[offset + i] = source[i] + vertex
    offset += source.length
    vertex += geometry.attributes.position.count
  }
  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.BufferAttribute(position, 3))
  geometry.setAttribute('normal', new THREE.BufferAttribute(normal, 3))
  geometry.setIndex(new THREE.Uint32BufferAttribute(index, 1))
  return geometry
}

function withScaleMorphs(geometry, sides) {
  const position = geometry.attributes.position
  const uniform = new Float32Array(position.count * 3)
  const width = new Float32Array(position.count * 3)
  for (let index = 0; index < position.count; index += 1) {
    const pivot = jointRest(`${sides[index]}_ankle`) || new THREE.Vector3()
    const x = position.getX(index) - pivot.x
    uniform[index * 3] = x
    uniform[index * 3 + 1] = position.getY(index) - pivot.y
    uniform[index * 3 + 2] = position.getZ(index) - pivot.z
    width[index * 3] = x
  }
  geometry.morphAttributes.position = [
    new THREE.Float32BufferAttribute(uniform, 3),
    new THREE.Float32BufferAttribute(width, 3),
  ]
}

function biasToe(geometry, sides) {
  const position = geometry.attributes.position
  const index = geometry.attributes.skinIndex
  const weight = geometry.attributes.skinWeight
  const range = { left: [Infinity, -Infinity], right: [Infinity, -Infinity] }
  for (let vertex = 0; vertex < position.count; vertex += 1) {
    const side = sides[vertex]
    const z = position.getZ(vertex)
    if (z < range[side][0]) range[side][0] = z
    if (z > range[side][1]) range[side][1] = z
  }
  const bones = { left: toeBone('left'), right: toeBone('right') }
  for (let vertex = 0; vertex < position.count; vertex += 1) {
    const side = sides[vertex]
    const span = range[side][1] - range[side][0] || 1
    const along = (position.getZ(vertex) - range[side][0]) / span
    if (along < 0.62 || bones[side] < 0) continue
    let channel = -1
    for (let slot = 0; slot < 4; slot += 1) if (index.getComponent(vertex, slot) === bones[side]) channel = slot
    if (channel < 0) {
      channel = 0
      for (let slot = 1; slot < 4; slot += 1) if (weight.getComponent(vertex, slot) < weight.getComponent(vertex, channel)) channel = slot
      index.setComponent(vertex, channel, bones[side])
    }
    weight.setComponent(vertex, channel, weight.getComponent(vertex, channel) + 0.12 + along * 0.18)
    let sum = 0
    for (let slot = 0; slot < 4; slot += 1) sum += weight.getComponent(vertex, slot)
    for (let slot = 0; slot < 4; slot += 1) weight.setComponent(vertex, slot, weight.getComponent(vertex, slot) / (sum || 1))
  }
}

function shoeGeometry(style) {
  const parts = []
  const sides = []
  const position = rig.mesh.geometry.attributes.position
  for (const side of ['left', 'right']) {
    const indices = footIndices(side)
    if (!indices.length) continue
    const min = new THREE.Vector3(Infinity, Infinity, Infinity)
    const max = new THREE.Vector3(-Infinity, -Infinity, -Infinity)
    const point = new THREE.Vector3()
    for (const index of indices) {
      point.fromBufferAttribute(position, index)
      min.min(point)
      max.max(point)
    }
    min.x -= 0.012
    max.x += 0.012
    min.z -= 0.008
    max.z += 0.012
    const boxes = []
    const soleTop = min.y + (style === 'sneaker' ? 0.018 : 0.012)
    if (style === 'heel') {
      const split = min.z + (max.z - min.z) * 0.42
      boxes.push([new THREE.Vector3(min.x, min.y - 0.062, min.z), new THREE.Vector3(max.x, soleTop, split)])
      boxes.push([new THREE.Vector3(min.x, min.y, split - 0.012), new THREE.Vector3(max.x, soleTop, max.z)])
      boxes.push([new THREE.Vector3(min.x, soleTop, min.z), new THREE.Vector3(max.x, max.y + 0.012, max.z)])
    } else if (style === 'sneaker') {
      boxes.push([new THREE.Vector3(min.x, min.y - 0.01, min.z), new THREE.Vector3(max.x, soleTop, max.z)])
      boxes.push([new THREE.Vector3(min.x, soleTop, min.z), new THREE.Vector3(max.x, max.y + 0.04, max.z)])
    } else {
      boxes.push([new THREE.Vector3(min.x, min.y, min.z), new THREE.Vector3(max.x, soleTop, max.z)])
      boxes.push([new THREE.Vector3(min.x, soleTop, min.z), new THREE.Vector3(max.x, max.y + 0.016, max.z)])
    }
    for (const [from, to] of boxes) {
      const before = parts.reduce((sum, geometry) => sum + geometry.attributes.position.count, 0)
      addBox(parts, from, to)
      const after = parts.reduce((sum, geometry) => sum + geometry.attributes.position.count, 0)
      for (let index = before; index < after; index += 1) sides.push(side)
    }
  }
  if (!parts.length) return null
  const geometry = mergeParts(parts)
  parts.forEach((geometry) => geometry.dispose())
  skinFromBody(geometry)
  biasToe(geometry, sides)
  withScaleMorphs(geometry, sides)
  return geometry
}

function wearSkinned(geometry, material) {
  const mesh = new THREE.SkinnedMesh(geometry, material)
  mesh.frustumCulled = false
  mesh.castShadow = true
  mesh.receiveShadow = true
  mesh.position.copy(rig.mesh.position)
  mesh.quaternion.copy(rig.mesh.quaternion)
  mesh.scale.copy(rig.mesh.scale)
  mesh.morphTargetInfluences = [0, 0]
  rig.mesh.parent.add(mesh)
  mesh.bind(rig.mesh.skeleton, rig.mesh.bindMatrix)
  return mesh
}

function ensureShoeHide() {
  const geometry = rig.mesh.geometry
  if (!geometry.getAttribute('shoeHide')) {
    geometry.setAttribute('shoeHide', new THREE.Float32BufferAttribute(new Float32Array(geometry.attributes.position.count), 1))
  }
  return geometry.getAttribute('shoeHide')
}

function installFootMask() {
  ensureShoeHide()
  const materials = Array.isArray(rig.mesh.material) ? rig.mesh.material : [rig.mesh.material]
  materials.forEach((material) => {
    if (!material || material.userData.footMask) return
    material.userData.footMask = true
    material.customProgramCacheKey = () => 'shoe-hide'
    material.onBeforeCompile = (shader) => {
      shader.vertexShader = shader.vertexShader
        .replace('#include <common>', '#include <common>\nattribute float shoeHide;\nvarying float vShoeHide;')
        .replace('#include <begin_vertex>', '#include <begin_vertex>\nvShoeHide = shoeHide;')
      shader.fragmentShader = shader.fragmentShader
        .replace('#include <common>', '#include <common>\nvarying float vShoeHide;')
        .replace('#include <dithering_fragment>', '#include <dithering_fragment>\nif (vShoeHide > 0.5) discard;')
    }
    material.needsUpdate = true
  })
}

function maskFeet(style) {
  const hide = ensureShoeHide()
  hide.array.fill(0)
  if (style) {
    const collar = style === 'sneaker' ? 1 : style === 'heel' ? 0.92 : 0.96
    const point = new THREE.Vector3()
    for (const side of ['left', 'right']) {
      const indices = footIndices(side)
      let minY = Infinity
      let maxY = -Infinity
      for (const index of indices) {
        morphedAt(index, point)
        if (point.y < minY) minY = point.y
        if (point.y > maxY) maxY = point.y
      }
      const limit = minY + (maxY - minY) * collar
      for (const index of indices) {
        morphedAt(index, point)
        if (point.y <= limit + 0.004) hide.setX(index, 1)
      }
    }
  }
  hide.needsUpdate = true
  maskSock(style)
}

function maskSock(style) {
  if (!thickSock) return
  const hide = thickSock.geometry.getAttribute('sockHide')
  const source = thickSock.userData.source
  const shoe = ensureShoeHide()
  for (let index = 0; index < hide.count; index += 1) hide.setX(index, style ? shoe.getX(source[index]) : 0)
  hide.needsUpdate = true
}

function footSize(morphed) {
  let length = 0
  let width = 0
  let count = 0
  const point = new THREE.Vector3()
  const position = rig.mesh.geometry.attributes.position
  for (const side of ['left', 'right']) {
    const indices = footIndices(side)
    if (!indices.length) continue
    let minX = Infinity
    let maxX = -Infinity
    let minZ = Infinity
    let maxZ = -Infinity
    for (const index of indices) {
      if (morphed) morphedAt(index, point)
      else point.fromBufferAttribute(position, index)
      if (point.x < minX) minX = point.x
      if (point.x > maxX) maxX = point.x
      if (point.z < minZ) minZ = point.z
      if (point.z > maxZ) maxZ = point.z
    }
    length += maxZ - minZ
    width += maxX - minX
    count += 1
  }
  return { length: length / (count || 1), width: width / (count || 1) }
}

function fitFootwear() {
  if (!rig?.smplx || !restFoot) return
  const current = footSize(true)
  const lengthRatio = current.length / (restFoot.length || 1)
  const widthRatio = current.width / (restFoot.width || 1)
  const uniform = THREE.MathUtils.clamp(lengthRatio - 1, -0.45, 0.65)
  const widthInfluence = THREE.MathUtils.clamp(widthRatio / Math.max(lengthRatio, 0.4) - 1, -0.6, 0.8)
  for (const mesh of Object.values(shoeMeshes)) {
    if (!mesh?.morphTargetInfluences) continue
    mesh.morphTargetInfluences[0] = uniform
    mesh.morphTargetInfluences[1] = widthInfluence
  }
  if (thickSock?.morphTargetInfluences) {
    thickSock.morphTargetInfluences[0] = uniform
    thickSock.morphTargetInfluences[1] = widthInfluence
  }
  maskFeet(activeShoe)
}

function tintThinSocks(mesh, colors) {
  const tint = new THREE.Color('#f4f1ec')
  const color = new THREE.Color()
  for (const index of sockIndices()) {
    color.setRGB(colors.getX(index), colors.getY(index), colors.getZ(index))
    color.lerp(tint, 0.88)
    colors.setXYZ(index, color.r, color.g, color.b)
  }
}

function knitTextures() {
  if (knitMap) return
  const canvas = document.createElement('canvas')
  canvas.width = 64
  canvas.height = 64
  const context = canvas.getContext('2d')
  context.fillStyle = '#f4f1ea'
  context.fillRect(0, 0, 64, 64)
  context.strokeStyle = '#d5cdc2'
  context.lineWidth = 1
  for (let y = 2; y < 64; y += 4) {
    context.beginPath()
    for (let x = 0; x <= 64; x += 2) context.lineTo(x, y + Math.sin((x + (y % 8)) * 0.5) * 1.1)
    context.stroke()
  }
  knitMap = new THREE.CanvasTexture(canvas)
  knitMap.wrapS = THREE.RepeatWrapping
  knitMap.wrapT = THREE.RepeatWrapping
  knitMap.repeat.set(8, 10)
  const bump = document.createElement('canvas')
  bump.width = 64
  bump.height = 64
  const bumpContext = bump.getContext('2d')
  bumpContext.fillStyle = '#8080ff'
  bumpContext.fillRect(0, 0, 64, 64)
  for (let y = 0; y < 64; y += 4) {
    bumpContext.fillStyle = y % 8 === 0 ? '#6a6aff' : '#9696ff'
    bumpContext.fillRect(0, y, 64, 2)
  }
  knitNormal = new THREE.CanvasTexture(bump)
  knitNormal.wrapS = THREE.RepeatWrapping
  knitNormal.wrapT = THREE.RepeatWrapping
  knitNormal.repeat.set(8, 10)
}

function discardSock(material) {
  material.onBeforeCompile = (shader) => {
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', '#include <common>\nattribute float sockHide;\nvarying float vSockHide;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvSockHide = sockHide;')
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <common>', '#include <common>\nvarying float vSockHide;')
      .replace('#include <dithering_fragment>', '#include <dithering_fragment>\nif (vSockHide > 0.5) discard;')
  }
}

function buildThickSock() {
  const geometry = rig.mesh.geometry
  const position = geometry.attributes.position
  const normal = geometry.attributes.normal
  const index = geometry.index
  if (!index || !normal) return
  const region = new Uint8Array(position.count)
  const sourceSide = new Array(position.count)
  for (const side of ['left', 'right']) {
    for (const vertex of sockIndices(side)) {
      region[vertex] = 1
      sourceSide[vertex] = side
    }
  }
  const map = new Int32Array(position.count).fill(-1)
  const faces = []
  for (let face = 0; face < index.count; face += 3) {
    const a = index.getX(face)
    const b = index.getX(face + 1)
    const c = index.getX(face + 2)
    if (region[a] && region[b] && region[c]) faces.push(a, b, c)
  }
  if (!faces.length) return
  let cursor = 0
  for (const vertex of faces) if (map[vertex] < 0) map[vertex] = cursor++
  const positions = new Float32Array(cursor * 3)
  const normals = new Float32Array(cursor * 3)
  const uv = new Float32Array(cursor * 2)
  const source = new Uint32Array(cursor)
  const sides = new Array(cursor)
  const point = new THREE.Vector3()
  const direction = new THREE.Vector3()
  let maxY = -Infinity
  for (let vertex = 0; vertex < position.count; vertex += 1) {
    const slot = map[vertex]
    if (slot < 0) continue
    point.fromBufferAttribute(position, vertex)
    direction.fromBufferAttribute(normal, vertex)
    if (direction.lengthSq() < 1e-8) direction.set(0, 1, 0)
    direction.normalize()
    point.addScaledVector(direction, 0.0035)
    positions[slot * 3] = point.x
    positions[slot * 3 + 1] = point.y
    positions[slot * 3 + 2] = point.z
    normals[slot * 3] = direction.x
    normals[slot * 3 + 1] = direction.y
    normals[slot * 3 + 2] = direction.z
    source[slot] = vertex
    sides[slot] = sourceSide[vertex] || (point.x >= 0 ? 'left' : 'right')
    if (point.y > maxY) maxY = point.y
  }
  for (let slot = 0; slot < cursor; slot += 1) {
    const y = positions[slot * 3 + 1]
    if (y > maxY - 0.012) {
      const extra = 0.004 * (1 - (maxY - y) / 0.012)
      positions[slot * 3] += normals[slot * 3] * extra
      positions[slot * 3 + 1] += extra * 0.35
      positions[slot * 3 + 2] += normals[slot * 3 + 2] * extra
    }
    uv[slot * 2] = Math.atan2(positions[slot * 3], positions[slot * 3 + 2]) / (Math.PI * 2) + 0.5
    uv[slot * 2 + 1] = positions[slot * 3 + 1] * 6
  }
  const shell = new THREE.BufferGeometry()
  shell.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  shell.setAttribute('normal', new THREE.BufferAttribute(normals, 3))
  shell.setAttribute('uv', new THREE.BufferAttribute(uv, 2))
  shell.setAttribute('sockHide', new THREE.Float32BufferAttribute(new Float32Array(cursor), 1))
  shell.setIndex(new THREE.Uint32BufferAttribute(faces.map((vertex) => map[vertex]), 1))
  skinFromBody(shell)
  withScaleMorphs(shell, sides)
  knitTextures()
  const material = new THREE.MeshStandardMaterial({
    color: 0xf7f4ef,
    map: knitMap,
    normalMap: knitNormal,
    roughness: 0.94,
    side: THREE.DoubleSide,
  })
  discardSock(material)
  thickSock = wearSkinned(shell, material)
  thickSock.userData.source = source
  thickSock.visible = activeSock === 'thick'
}

function buildFootwear() {
  try {
    for (const mesh of Object.values(shoeMeshes)) mesh.removeFromParent()
    thickSock?.removeFromParent()
    for (const key of Object.keys(shoeMeshes)) delete shoeMeshes[key]
    thickSock = null
    footwearCache = null
    restFoot = null
    if (!rig?.smplx) return
    installFootMask()
    restFoot = footSize(false)
    const colors = { flat: 0x243056, sneaker: 0xe7e7e4, heel: 0x161616 }
    for (const style of ['flat', 'sneaker', 'heel']) {
      const geometry = shoeGeometry(style)
      if (!geometry) continue
      const material = new THREE.MeshStandardMaterial({
        color: colors[style],
        roughness: style === 'sneaker' ? 0.74 : 0.52,
        metalness: style === 'heel' ? 0.08 : 0,
        polygonOffset: true,
        polygonOffsetFactor: -2,
        polygonOffsetUnits: -2,
      })
      const mesh = wearSkinned(geometry, material)
      mesh.renderOrder = 2
      mesh.visible = activeShoe === style
      shoeMeshes[style] = mesh
    }
    buildThickSock()
    fitFootwear()
  } catch (error) {
    console.error(error)
  }
}

function fingerFit(boneName, childName) {
  const origin = jointRest(boneName)
  const child = rig.bones[childName]
  if (!origin || !child) return null
  const axis = child.position.clone()
  const length = axis.length() || 1
  axis.multiplyScalar(1 / length)
  const weights = boneWeights(rig.mesh, [boneName])
  const point = new THREE.Vector3()
  const radii = []
  const center = new THREE.Vector3()
  for (let index = 0; index < weights.length; index += 1) {
    if (weights[index] < 0.45) continue
    morphedAt(index, point).sub(origin)
    const along = point.dot(axis)
    if (along < length * 0.3 || along > length * 0.8) continue
    point.addScaledVector(axis, -along)
    const radial = point.length()
    if (radial < 0.004 || radial > 0.028) continue
    radii.push(radial)
    center.add(point)
  }
  if (!radii.length) return { radius: 0.012, center: new THREE.Vector3(), axis, length }
  center.multiplyScalar(1 / radii.length)
  radii.sort((a, b) => a - b)
  return { radius: radii[Math.min(radii.length - 1, Math.floor(radii.length * 0.8))], center, axis, length }
}

function fitAccessories() {
  if (!rig?.smplx || !accessories.length) return
  const point = new THREE.Vector3()
  const leftEar = accessories.find((item) => item.userData.extra === 'earrings' && item.userData.side === 'left')
  const rightEar = accessories.find((item) => item.userData.extra === 'earrings' && item.userData.side === 'right')
  let headScale = 1
  if (leftEar && rightEar) {
    const width = morphedAt(leftEar.userData.anchor, point).distanceTo(morphedAt(rightEar.userData.anchor, new THREE.Vector3()))
    if (!leftEar.userData.restWidth) leftEar.userData.restWidth = width || 1
    headScale = width / leftEar.userData.restWidth
  }
  const handScale = 1 + shapeNumber('hands') / 220
  for (const item of accessories) {
    if (item.userData.ring && item.userData.childBone) {
      const fit = fingerFit(item.parent?.name, item.userData.childBone)
      if (!fit) continue
      item.quaternion.setFromUnitVectors(new THREE.Vector3(1, 0, 0), fit.axis)
      item.position.copy(fit.axis).multiplyScalar(fit.length * 0.55).add(fit.center)
      item.scale.setScalar(fit.radius / (item.userData.hole || 0.0156))
      continue
    }
    if (item.userData.anchor == null || !item.parent) continue
    const rest = jointRest(item.userData.boneName)
    if (!rest) continue
    morphedAt(item.userData.anchor, point).sub(rest).add(item.userData.extraOffset)
    item.position.copy(point)
    const scale = item.userData.handScaled ? handScale : headScale
    item.scale.setScalar(scale)
  }
}

function skinFromBody(geometry) {
  const bodyPosition = rig.mesh.geometry.attributes.position
  const bodyJoints = rig.mesh.geometry.attributes.skinIndex
  const bodyWeights = rig.mesh.geometry.attributes.skinWeight
  const position = geometry.attributes.position
  const index = new Uint16Array(position.count * 4)
  const weight = new Float32Array(position.count * 4)
  const point = new THREE.Vector3()
  const bodyPoint = new THREE.Vector3()
  for (let vertex = 0; vertex < position.count; vertex += 1) {
    point.fromBufferAttribute(position, vertex)
    let nearest = 0
    let nearestDistance = Infinity
    for (let body = 0; body < bodyPosition.count; body += 1) {
      bodyPoint.fromBufferAttribute(bodyPosition, body)
      const distance = point.distanceToSquared(bodyPoint)
      if (distance < nearestDistance) {
        nearestDistance = distance
        nearest = body
      }
    }
    for (let channel = 0; channel < 4; channel += 1) {
      index[vertex * 4 + channel] = bodyJoints.getComponent(nearest, channel)
      weight[vertex * 4 + channel] = bodyWeights.getComponent(nearest, channel)
    }
  }
  geometry.setAttribute('skinIndex', new THREE.Uint16BufferAttribute(index, 4))
  geometry.setAttribute('skinWeight', new THREE.Float32BufferAttribute(weight, 4))
}

function makeSpring(parent, local, length) {
  const bone = new THREE.Object3D()
  bone.position.copy(local)
  parent.add(bone)
  const spring = { bone, length, tail: null, prev: null, extras: [] }
  springBones.push(spring)
  return spring
}

function stepSprings(dt) {
  const settle = 1 - Math.pow(0.12, Math.max(dt, 0.001) * 60)
  for (const spring of springBones) {
    const parent = spring.bone.parent
    if (!parent) continue
    parent.updateWorldMatrix(true, false)
    const origin = new THREE.Vector3()
    spring.bone.getWorldPosition(origin)
    const rest = parent.localToWorld(spring.bone.position.clone().add(new THREE.Vector3(0, -spring.length, 0)))
    if (!spring.tail) {
      spring.tail = rest.clone()
      spring.prev = rest.clone()
    }
    const velocity = spring.tail.clone().sub(spring.prev).multiplyScalar(0.84)
    spring.prev.copy(spring.tail)
    spring.tail.add(velocity)
    spring.tail.lerp(rest, settle)
    const offset = spring.tail.clone().sub(origin)
    if (offset.lengthSq() < 1e-8) continue
    offset.setLength(spring.length)
    spring.tail.copy(origin).add(offset)
    const local = parent.worldToLocal(spring.tail.clone()).sub(spring.bone.position)
    spring.bone.rotation.x = Math.atan2(local.z, Math.max(0.001, -local.y))
    spring.bone.rotation.z = Math.atan2(-local.x, Math.max(0.001, -local.y))
  }
}

function kickSprings() {
  if (springTimer) return
  let last = performance.now()
  const tick = (now) => {
    const live = springBones.some((spring) => spring.extras.some((item) => item.visible))
    if (!live) {
      springTimer = 0
      return
    }
    const dt = Math.min(0.05, (now - last) / 1000)
    last = now
    stepSprings(dt)
    render()
    springTimer = requestAnimationFrame(tick)
  }
  springTimer = requestAnimationFrame(tick)
}

function paintHairExtras() {
  const color = new THREE.Color(hairColors[hairChoice] || hairColors.brown)
  for (const item of accessories) {
    if (!item.userData.hair) continue
    item.traverse((child) => {
      if (child.material?.color) child.material.color.copy(color)
    })
  }
}

let humanAssets = null

async function loadHumanAssets() {
  if (humanAssets) return humanAssets
  const [glasses, left, right, ring] = await Promise.all([
    loader.loadAsync('/garments/makehuman/glasses.glb?v=2'),
    loader.loadAsync('/garments/makehuman/earring-left.glb?v=2'),
    loader.loadAsync('/garments/makehuman/earring-right.glb?v=2'),
    loader.loadAsync('/garments/makehuman/ring.glb?v=2'),
  ])
  humanAssets = { glasses, left, right, ring }
  return humanAssets
}

function assetMesh(gltf, shift) {
  let source = null
  gltf.scene.traverse((child) => {
    if (child.isMesh && !source) source = child
  })
  const mesh = source.clone()
  mesh.geometry = source.geometry.clone()
  if (shift) mesh.geometry.translate(shift.x, shift.y, shift.z)
  mesh.material = source.material
  if (mesh.material) mesh.material.side = THREE.DoubleSide
  mesh.castShadow = true
  mesh.frustumCulled = false
  return mesh
}

async function buildAccessories() {
  accessories.length = 0
  springBones.length = 0
  const assets = await loadHumanAssets().catch((error) => {
    console.error(error)
    return null
  })
  const headBone = rig.bones.head
  const head = jointRest('head')
  const neck = jointRest('neck')
  if (!headBone || !head || !neck) return
  const gold = new THREE.MeshStandardMaterial({ color: 0xc6a15a, roughness: 0.28, metalness: 0.7 })
  const hairMat = new THREE.MeshStandardMaterial({ color: hairColors[hairChoice] || hairColors.brown, roughness: 0.72 })
  const cloth = new THREE.MeshStandardMaterial({ color: 0x8e3b3b, roughness: 0.78, side: THREE.DoubleSide })

  const eyes = jointRest('left_eye_smplhf') && jointRest('right_eye_smplhf')
    ? jointRest('left_eye_smplhf').add(jointRest('right_eye_smplhf')).multiplyScalar(0.5)
    : head.clone().add(new THREE.Vector3(0, 0.03, 0.07))
  if (assets?.glasses) {
    const glasses = assetMesh(assets.glasses, new THREE.Vector3(0, -0.00144, -0.05434))
    headBone.add(trackAccessory(glasses, 'glasses', vertexNear(eyes), 'head', new THREE.Vector3(0, 0, 0.001)))
  }

  if (assets?.left && assets?.right) {
    const left = assetMesh(assets.left)
    left.userData.side = 'left'
    headBone.add(trackAccessory(left, 'earrings', earVertex(1), 'head', new THREE.Vector3(0.0015, 0, 0)))
    const right = assetMesh(assets.right)
    right.userData.side = 'right'
    headBone.add(trackAccessory(right, 'earrings', earVertex(-1), 'head', new THREE.Vector3(-0.0015, 0, 0)))
  }

  if (assets?.ring && rig.bones.left_ring1 && rig.bones.left_ring2) {
    const ring = assetMesh(assets.ring)
    ring.userData.ring = true
    ring.userData.hole = 0.01555
    ring.userData.childBone = 'left_ring2'
    ring.userData.extra = 'ring'
    ring.visible = false
    rig.bones.left_ring1.add(ring)
    accessories.push(ring)
  }

  const necklaceGeo = new THREE.TorusGeometry(0.064, 0.0055, 8, 28)
  necklaceGeo.rotateX(Math.PI / 2)
  necklaceGeo.translate(neck.x, neck.y - 0.01, neck.z)
  skinFromBody(necklaceGeo)
  const necklace = new THREE.SkinnedMesh(necklaceGeo, gold)
  necklace.bind(rig.mesh.skeleton)
  necklace.userData.extra = 'necklace'
  necklace.userData.soft = true
  necklace.visible = false
  necklace.frustumCulled = false
  rig.root.add(necklace)
  accessories.push(necklace)
  const pendantSpring = makeSpring(rig.bones.neck, new THREE.Vector3(0, -0.02, 0.055), 0.045)
  const pendant = new THREE.Mesh(new THREE.SphereGeometry(0.012, 12, 10), gold)
  pendant.position.y = -0.045
  pendant.userData.extra = 'necklace'
  pendant.visible = false
  pendantSpring.bone.add(pendant)
  pendantSpring.extras.push(necklace, pendant)
  accessories.push(pendant)

  const scarfGeo = new THREE.TorusGeometry(0.082, 0.013, 6, 20)
  scarfGeo.rotateX(Math.PI / 2)
  scarfGeo.translate(neck.x, neck.y - 0.035, neck.z + 0.01)
  skinFromBody(scarfGeo)
  const scarf = new THREE.SkinnedMesh(scarfGeo, cloth)
  scarf.bind(rig.mesh.skeleton)
  scarf.userData.extra = 'scarf'
  scarf.userData.soft = true
  scarf.visible = false
  scarf.frustumCulled = false
  rig.root.add(scarf)
  accessories.push(scarf)
  const scarfSpring = makeSpring(rig.bones.neck, new THREE.Vector3(0.02, -0.04, 0.06), 0.08)
  const scarfEnd = new THREE.Mesh(new THREE.BoxGeometry(0.03, 0.08, 0.008), cloth)
  scarfEnd.position.y = -0.08
  scarfEnd.userData.extra = 'scarf'
  scarfEnd.visible = false
  scarfSpring.bone.add(scarfEnd)
  scarfSpring.extras.push(scarf, scarfEnd)
  accessories.push(scarfEnd)

  const crown = vertexNear(head.clone().add(new THREE.Vector3(0, 0.12, 0)))
  const short = new THREE.Mesh(new THREE.SphereGeometry(0.092, 18, 14), hairMat)
  short.scale.set(1, 0.72, 0.82)
  short.userData.hair = true
  headBone.add(trackAccessory(short, 'hair-short', crown, 'head', new THREE.Vector3(0, -0.01, -0.012)))
  const bun = new THREE.Mesh(new THREE.SphereGeometry(0.042, 14, 12), hairMat.clone())
  bun.userData.hair = true
  headBone.add(trackAccessory(bun, 'hair-bun', crown, 'head', new THREE.Vector3(0, 0.01, -0.07)))
  const braid = new THREE.Group()
  braid.userData.hair = true
  for (let knot = 0; knot < 5; knot += 1) {
    const bead = new THREE.Mesh(new THREE.SphereGeometry(0.02 - knot * 0.002, 10, 8), hairMat.clone())
    bead.position.set(0, -0.03 - knot * 0.034, -0.01 - knot * 0.008)
    braid.add(bead)
  }
  headBone.add(trackAccessory(braid, 'hair-braid', crown, 'head', new THREE.Vector3(0, 0.02, -0.055)))
  fitAccessories()
  buildFootwear()
}

function coverHead(garment, body) {
  const position = garment.geometry.attributes.position
  const skin = body.geometry.attributes.position
  let minY = Infinity
  let maxY = -Infinity
  for (let index = 0; index < position.count; index += 1) {
    const y = position.getY(index)
    if (y < minY) minY = y
    if (y > maxY) maxY = y
  }
  let axisX = 0
  let axisZ = 0
  let axisCount = 0
  for (let index = 0; index < position.count; index += 1) {
    if (position.getY(index) > minY + 0.012) continue
    axisX += position.getX(index)
    axisZ += position.getZ(index)
    axisCount += 1
  }
  if (!axisCount) return
  axisX /= axisCount
  axisZ /= axisCount
  let crown = 0
  for (let index = 0; index < position.count; index += 1) {
    const y = position.getY(index)
    if (y < minY + 0.03 || y > minY + 0.09) continue
    crown = Math.max(crown, Math.hypot(position.getX(index) - axisX, position.getZ(index) - axisZ))
  }
  if (crown < 0.04) return
  const bins = 72
  const reach = new Array(bins).fill(0)
  for (let index = 0; index < skin.count; index += 1) {
    const y = skin.getY(index)
    if (y < minY + 0.004 || y > maxY + 0.02) continue
    const x = skin.getX(index) - axisX
    const z = skin.getZ(index) - axisZ
    const radius = Math.hypot(x, z)
    if (radius > 0.2) continue
    const bin = Math.round(((Math.atan2(z, x) + Math.PI) / (Math.PI * 2)) * bins) % bins
    if (radius > reach[bin]) reach[bin] = radius
  }
  const spread = reach.slice()
  for (let index = 0; index < bins; index += 1) {
    reach[index] = Math.max(spread[index], spread[(index + bins - 1) % bins], spread[(index + 1) % bins])
  }
  for (let index = 0; index < position.count; index += 1) {
    const x = position.getX(index) - axisX
    const z = position.getZ(index) - axisZ
    const bin = Math.round(((Math.atan2(z, x) + Math.PI) / (Math.PI * 2)) * bins) % bins
    const factor = Math.min(1.12, Math.max(1, (reach[bin] + 0.006) / crown))
    if (factor === 1) continue
    position.setX(index, axisX + x * factor)
    position.setZ(index, axisZ + z * factor)
  }
  const span = Math.max(0.05, maxY - minY)
  for (let index = 0; index < position.count; index += 1) {
    const y = position.getY(index)
    const front = Math.min(1, Math.max(0, (position.getZ(index) - axisZ) / crown))
    const along = 1 - (y - minY) / span
    position.setY(index, y - 0.012 * front * along)
  }
  position.needsUpdate = true
  garment.geometry.computeVertexNormals()
}

async function addGarments(root) {
  const body = rig?.mesh
  if (!body?.skeleton) return
  const garmentLoader = new GLTFLoader()
  for (const [url, color, wear] of garmentFiles) {
    try {
      const gltf = await garmentLoader.loadAsync(`${url}?v=85`)
      const meshes = []
      gltf.scene.traverse((child) => {
        if (child.isSkinnedMesh) meshes.push(child)
      })
      for (const child of meshes) {
        const map = child.material?.map || null
        const normalMap = child.material?.normalMap || null
        const hasColors = Boolean(child.geometry.attributes.color)
        child.material = new THREE.MeshStandardMaterial({
          color: map || hasColors ? 0xffffff : color,
          map,
          normalMap,
          vertexColors: hasColors,
          roughness: wear === 'bag' ? 0.45 : 0.72,
          metalness: wear === 'bag' ? 0.08 : 0,
          skinning: true,
          side: THREE.DoubleSide,
        })
        child.frustumCulled = false
        child.bind(body.skeleton, child.bindMatrix)
        if (wear === 'hat') coverHead(child, body)
        child.userData.garment = true
        child.userData.wear = wear
        child.userData.rigid = Boolean(wear)
        child.visible = !wear || worn[wear] !== false
        const bound = child.geometry.attributes.position.array
        child.userData.bindPos = bound.slice()
        child.userData.clothPos = bound.slice()
        child.userData.clothVel = new Float32Array(bound.length)
        root.add(child)
      }
    } catch (error) {
      console.error(url, error)
      showError(`${url}: ${error?.stack || error}`)
    }
  }
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
  accessories.length = 0
  springBones.length = 0
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
      if (String(url).includes('smplx_thin') || String(url).includes('smplx_body')) await addGarments(object)
      await buildAccessories()
      skeletonHelper = new THREE.SkeletonHelper(skinned)
      skeletonHelper.visible = document.getElementById('skeleton')?.checked !== false
      group.add(skeletonHelper)
      object.updateMatrixWorld(true)
      const box = new THREE.Box3().setFromObject(skinned)
      restHeight = Math.max(0.2, box.max.y - box.min.y)
      if (!options.keepShape) resetShapeSliders()
      applyNamedPreset('front')
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
function applyNamedPreset(name) {
  const preset = posePresets[name] || {}
  applyingPreset = true
  document.querySelectorAll('[data-pose]').forEach((input) => {
    input.value = '0'
  })
  Object.entries(preset).forEach(([key, value]) => {
    const input = document.querySelector(`[data-pose="${key}"]`)
    if (input) input.value = String(value)
  })
  document.querySelectorAll('[data-preset]').forEach((button) => {
    button.classList.toggle('active', button.dataset.preset === name)
  })
  applyingPreset = false
  applyPose()
}

document.getElementById('reset-pose')?.addEventListener('click', () => {
  applyNamedPreset('front')
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
const CLOTHES_SERVICE = 'http://127.0.0.1:8891'

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
    paintHairExtras()
    render()
  })
})
document.querySelectorAll('[data-shoe]').forEach((button) => {
  button.addEventListener('click', () => {
    const name = button.dataset.shoe
    activeShoe = activeShoe === name ? null : name
    document.querySelectorAll('[data-shoe]').forEach((item) => item.classList.toggle('active', item.dataset.shoe === activeShoe))
    for (const [style, mesh] of Object.entries(shoeMeshes)) mesh.visible = style === activeShoe
    applyPose()
    render()
  })
})
document.querySelectorAll('[data-sock]').forEach((button) => {
  button.addEventListener('click', () => {
    const name = button.dataset.sock
    activeSock = activeSock === name ? null : name
    document.querySelectorAll('[data-sock]').forEach((item) => item.classList.toggle('active', item.dataset.sock === activeSock))
    if (thickSock) thickSock.visible = activeSock === 'thick'
    paintColors()
    fitFootwear()
    render()
  })
})
document.querySelectorAll('[data-extra]').forEach((button) => {
  button.addEventListener('click', () => {
    const name = button.dataset.extra
    const items = accessories.filter((item) => item.userData.extra === name)
    const show = items.some((item) => !item.visible)
    items.forEach((item) => { item.visible = show })
    button.classList.toggle('active', show)
    if (show && items.some((item) => item.userData.soft || springBones.some((spring) => spring.extras.includes(item)))) kickSprings()
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
document.querySelectorAll('[data-wear]').forEach((button) => {
  button.addEventListener('click', () => {
    const name = button.dataset.wear
    worn[name] = !worn[name]
    document.querySelectorAll(`[data-wear="${name}"]`).forEach((item) => item.classList.toggle('active', worn[name]))
    group.traverse((child) => {
      if (child.userData?.wear === name) child.visible = worn[name]
    })
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
    document.querySelectorAll('[data-preset]').forEach((item) => {
      item.classList.toggle('active', item.dataset.preset === button.dataset.preset)
    })
    applyingPreset = false
    applyPose()
    settleCloth()
  })
})
document.querySelectorAll('[data-builder]').forEach((button) => {
  button.addEventListener('click', () => {
    clothBuilder = button.dataset.builder
    document.querySelectorAll('[data-builder]').forEach((item) => item.classList.toggle('active', item === button))
  })
})
document.getElementById('clothes-motion')?.addEventListener('click', () => {
  const sequence = ['front', 'glance', 'casual', 'front']
  let frame = 0
  const play = () => {
    const name = sequence[Math.min(sequence.length - 1, Math.floor(frame / 18))]
    const preset = posePresets[name] || {}
    document.querySelectorAll('[data-pose]').forEach((input) => { input.value = '0' })
    Object.entries(preset).forEach(([key, value]) => {
      const input = document.querySelector(`[data-pose="${key}"]`)
      if (input) input.value = String(value)
    })
    applyPose()
    stepCloth(1 / 30)
    render()
    frame += 1
    if (frame < sequence.length * 18) requestAnimationFrame(play)
  }
  play()
})
document.getElementById('clothes-photo')?.addEventListener('change', (event) => {
  const file = event.target.files?.[0]
  const fit = document.getElementById('fit')
  if (file && fit) fit.textContent = `${file.name} is ready. Render with ReMU sends it to the clothes server.`
})
document.getElementById('clothes-from-photo')?.addEventListener('click', async () => {
  const fit = document.getElementById('fit')
  const clothes = document.getElementById('clothes-photo')?.files?.[0] || photoFiles[0]
  if (!clothes) {
    showError('Choose a clothes photo first.')
    return
  }
  showError('')
  if (fit) fit.textContent = `Sending ${clothes.name} to ReMU (${clothBuilder}).`
  try {
    const saved = await fetch(`${CLOTHES_SERVICE}/from-photo?builder=${encodeURIComponent(clothBuilder)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/octet-stream' },
      body: clothes,
    })
    const detail = (await saved.text()).trim()
    if (!saved.ok) throw new Error(detail || `Clothes service returned ${saved.status}`)
    if (fit) fit.textContent = detail
    const watch = async () => {
      for (let attempt = 0; attempt < 40; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, 4000))
        const status = await fetch(`${CLOTHES_SERVICE}/status`)
        const text = (await status.text()).trim()
        if (fit) fit.textContent = text
        if (/stopped|ready|meshes are in/i.test(text)) break
      }
    }
    watch().catch(() => {})
  } catch (error) {
    showError(error instanceof Error ? error.message : 'The clothes service is not running.')
  }
})
function showPanel(id) {
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
