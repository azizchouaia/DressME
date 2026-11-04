const API = 'http://127.0.0.1:8893/api'
const STEPS = {
  avatar: [
    'Checking the photos',
    'Uploading to the GPU',
    'Reconstructing in 3D (about 20 minutes)',
    'Downloading the 3D result',
    'Fitting the clothes to the avatar',
    'Choosing a hairstyle',
    'Printing the face and skin tone',
    'Done',
  ],
  outfit: [
    'Checking the photos',
    'Uploading to the GPU',
    'Reconstructing in 3D (about 20 minutes)',
    'Downloading the 3D result',
    'Fitting the clothes to the avatar',
    'Done',
  ],
}

const $ = (selector) => document.querySelector(selector)
const BUILD = { slim: -100, average: -33, athletic: 33, heavy: 100 }

const state = { users: [], user: null, wearing: null, gender: 'male', shape: 'slim', photos: { create: {}, outfit: {} }, viewerReady: false, pendingLook: null }

async function api(path, options = {}) {
  let response
  try {
    response = await fetch(`${API}${path}`, options)
  } catch {
    throw new Error('The studio server is not running. Start it with: py -3 ai/remu/studio_server.py')
  }
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.error || 'Something went wrong.')
  return data
}

function show(name) {
  document.querySelectorAll('.screen').forEach((screen) => screen.classList.toggle('on', screen.id === `screen-${name}`))
}

function photoSlots(kind) {
  const holder = document.querySelector(`[data-photos="${kind}"]`)
  holder.innerHTML = ''
  for (const slot of ['front', 'back']) {
    const node = $('#photo-slot').content.firstElementChild.cloneNode(true)
    node.querySelector('b').textContent = slot === 'front' ? 'Front photo' : 'Back photo'
    const input = node.querySelector('input')
    const image = node.querySelector('img')
    input.addEventListener('change', () => {
      const file = input.files?.[0]
      if (!file) return
      state.photos[kind][slot] = file
      image.src = URL.createObjectURL(file)
      image.hidden = false
    })
    holder.append(node)
  }
}

async function uploadPhotos(user, kind) {
  for (const slot of ['front', 'back']) {
    const file = state.photos[kind][slot]
    if (!file) throw new Error(`Add the ${slot} photo.`)
    await api(`/users/${user}/photo?slot=${slot}`, { method: 'POST', body: file })
  }
}

// --- 3D viewer -------------------------------------------------------------

const viewer = $('#viewer')
window.addEventListener('message', (event) => {
  let data = event.data
  try {
    data = typeof data === 'string' ? JSON.parse(data) : data
  } catch {
    return
  }
  if (data?.type === 'ready') {
    state.viewerReady = true
    if (state.pendingLook) sendLook(state.pendingLook)
  }
  if (data?.type === 'look-ready') $('#stage-busy').style.display = 'none'
})

function sendLook(look) {
  state.pendingLook = look
  if (!state.viewerReady) return
  $('#stage-busy').textContent = 'Dressing your avatar...'
  $('#stage-busy').style.display = 'block'
  viewer.contentWindow.postMessage(JSON.stringify({ type: 'look', ...look }), '*')
}

function morphsFor(user) {
  return { build: BUILD[user.shape] ?? 0 }
}

function lookFor(user, pieces) {
  return { url: user.avatar, height: user.height, hair: user.hair, profile: user.profile, wear: pieces, gender: user.gender, shape: morphsFor(user) }
}

function applyBody() {
  const user = state.user
  if (!user) return
  $('#home-meta').textContent = `${user.gender === 'female' ? 'Female' : 'Male'} · ${Math.round(user.height)} cm · ${Math.round(user.weight)} kg · ${(user.shape || 'average')[0].toUpperCase()}${(user.shape || 'average').slice(1)}`
  viewer.contentWindow?.postMessage(JSON.stringify({ type: 'body', height: user.height, gender: user.gender, shape: morphsFor(user) }), '*')
}

function wear(outfit) {
  const user = state.user
  state.wearing = outfit?.id || null
  localStorage.setItem(`dressme.wearing.${user.id}`, state.wearing || '')
  $('#stage-title').textContent = outfit ? outfit.name : 'No clothes'
  sendLook(lookFor(user, outfit ? outfit.pieces : []))
  renderOutfits()
}

// --- screens ---------------------------------------------------------------

function renderUsers() {
  const list = $('#user-list')
  list.innerHTML = ''
  for (const user of state.users) {
    const card = document.createElement('button')
    card.type = 'button'
    card.className = 'user'
    const skin = user.profile?.skin || '#c9a58c'
    const status = user.ready ? `${user.outfits.length} saved outfit${user.outfits.length === 1 ? '' : 's'}` : 'Avatar not built yet'
    card.innerHTML = `<div class="face" style="background:${skin}"></div><h3></h3><div class="muted"></div>`
    card.querySelector('h3').textContent = user.name
    card.querySelector('.muted').textContent = status
    card.addEventListener('click', () => openUser(user.id))
    list.append(card)
  }
  const add = document.createElement('button')
  add.type = 'button'
  add.className = 'user new'
  add.textContent = '+ New avatar'
  add.addEventListener('click', () => startCreate(true))
  list.append(add)
}

function startCreate(cancellable) {
  state.photos.create = {}
  photoSlots('create')
  $('#create-form').reset()
  $('#create-error').textContent = ''
  $('#create-cancel').hidden = !cancellable
  show('create')
}

document.querySelectorAll('[data-gender]').forEach((button) => {
  button.addEventListener('click', () => {
    state.gender = button.dataset.gender
    document.querySelectorAll('[data-gender]').forEach((item) => item.classList.toggle('on', item === button))
  })
})
document.querySelectorAll('[data-shape]').forEach((button) => {
  button.addEventListener('click', () => {
    state.shape = button.dataset.shape
    document.querySelectorAll('[data-shape]').forEach((item) => item.classList.toggle('on', item === button))
  })
})

$('#create-cancel').addEventListener('click', () => {
  renderUsers()
  show('users')
})

$('#create-form').addEventListener('submit', async (event) => {
  event.preventDefault()
  const form = new FormData(event.target)
  const button = event.target.querySelector('[type="submit"]')
  $('#create-error').textContent = ''
  if (!state.photos.create.front || !state.photos.create.back) {
    $('#create-error').textContent = 'Add both the front and the back photo.'
    return
  }
  button.disabled = true
  try {
    const user = await api('/users', {
      method: 'POST',
      body: JSON.stringify({ name: form.get('name'), gender: state.gender, height: Number(form.get('height')), weight: Number(form.get('weight')), shape: state.shape }),
    })
    await uploadPhotos(user.id, 'create')
    await api(`/users/${user.id}/build?kind=avatar&mirror=${form.get('mirror') ? 1 : 0}`, { method: 'POST' })
    state.user = user
    watchBuild('avatar')
  } catch (error) {
    $('#create-error').textContent = error.message
  } finally {
    button.disabled = false
  }
})

// --- build progress --------------------------------------------------------

let buildTimer = 0

function watchBuild(kind) {
  $('#build-title').textContent = kind === 'avatar' ? 'Building your avatar' : 'Building your new outfit'
  $('#build-error').textContent = ''
  $('#build-retry').hidden = true
  show('build')
  clearInterval(buildTimer)
  const tick = async () => {
    let job
    try {
      job = await api('/job')
    } catch (error) {
      $('#build-error').textContent = error.message
      return
    }
    const steps = STEPS[job.kind || kind]
    const at = Math.max(0, steps.indexOf(job.step))
    $('#build-steps').innerHTML = steps
      .map((step, index) => `<li class="${job.done || index < at ? 'done' : index === at && !job.error ? 'now' : ''}">${step}</li>`)
      .join('')
    const minutes = Math.floor((job.seconds || 0) / 60)
    $('#build-time').textContent = `${minutes} min ${(job.seconds || 0) % 60} s`
    $('#build-log').textContent = (job.lines || []).join('\n')
    if (job.error) {
      clearInterval(buildTimer)
      $('#build-error').textContent = job.error
      $('#build-retry').hidden = false
      return
    }
    if (job.done && !job.busy) {
      clearInterval(buildTimer)
      await openUser(job.user, { draft: true })
    }
  }
  tick()
  buildTimer = setInterval(tick, 3000)
}

$('#build-log-toggle').addEventListener('click', () => {
  const log = $('#build-log')
  log.hidden = !log.hidden
  $('#build-log-toggle').textContent = log.hidden ? 'Show details' : 'Hide details'
})

$('#build-back').addEventListener('click', async () => {
  if (state.user?.ready) await openUser(state.user.id)
  else await boot()
})

// --- home ------------------------------------------------------------------

async function openUser(id, options = {}) {
  const user = await api(`/users/${id}`)
  state.user = user
  if (!user.ready) {
    const job = await api('/job').catch(() => ({}))
    if (job.busy && job.user === id) return watchBuild(job.kind)
    state.photos.create = {}
    photoSlots('create')
    show('create')
    $('#create-error').textContent = 'This avatar was not finished. Fill in the form again to build it.'
    return
  }
  $('#home-name').textContent = user.name
  $('#home-meta').textContent = `${user.gender === 'female' ? 'Female' : 'Male'} · ${Math.round(user.height)} cm · ${Math.round(user.weight)} kg · ${(user.shape || 'average')[0].toUpperCase()}${(user.shape || 'average').slice(1)}`
  localStorage.setItem('dressme.user', user.id)
  fillBody()
  renderHair()
  show('home')
  if (!viewer.src) {
    viewer.addEventListener('load', () => {
      if (state.pendingLook) sendLook(state.pendingLook)
    })
    viewer.src = '/viewer/index.html?embed=1&v=178'
  }
  const saved = localStorage.getItem(`dressme.wearing.${user.id}`)
  const outfit = options.draft && user.draft ? user.draft : user.outfits.find((item) => item.id === saved) || user.draft || user.outfits[0] || null
  selectTab('wardrobe')
  wear(outfit)
  $('#draft-name').value = user.outfits.length ? '' : 'My first outfit'
}

function renderOutfits() {
  const user = state.user
  const draft = user.draft
  $('#draft').hidden = !draft
  const list = $('#outfit-list')
  list.innerHTML = ''
  const items = [{ id: null, name: 'No clothes', pieces: [], photo: null }, ...(draft ? [draft] : []), ...user.outfits]
  for (const outfit of items) {
    const card = document.createElement('button')
    card.type = 'button'
    card.className = `outfit${state.wearing === outfit.id ? ' on' : ''}`
    card.innerHTML = '<div class="thumb"></div><div class="name"><span></span></div>'
    const thumb = card.querySelector('.thumb')
    if (outfit.photo) thumb.style.backgroundImage = `url("${outfit.photo}")`
    else thumb.textContent = outfit.id ? '' : 'Body only'
    card.querySelector('.name span').textContent = outfit.id === '_draft' ? 'New (not saved)' : outfit.name
    if (outfit.id && outfit.id !== '_draft') {
      const remove = document.createElement('span')
      remove.className = 'remove'
      remove.title = 'Delete'
      remove.textContent = '×'
      remove.addEventListener('click', async (event) => {
        event.stopPropagation()
        if (!confirm(`Delete "${outfit.name}"?`)) return
        state.user = await api(`/users/${user.id}/outfits/${outfit.id}`, { method: 'DELETE' })
        if (state.wearing === outfit.id) wear(null)
        else renderOutfits()
      })
      card.querySelector('.name').append(remove)
    }
    card.addEventListener('click', () => wear(outfit))
    list.append(card)
  }
  const add = document.createElement('button')
  add.type = 'button'
  add.className = 'outfit add'
  add.textContent = '+ Add outfit'
  add.addEventListener('click', () => {
    const panel = $('#add-outfit')
    panel.hidden = !panel.hidden
    if (!panel.hidden) panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  })
  list.append(add)
}

$('#draft-save').addEventListener('click', async () => {
  const name = $('#draft-name').value.trim() || 'Outfit'
  const user = await api(`/users/${state.user.id}/outfits`, { method: 'POST', body: JSON.stringify({ name }) })
  state.user = user
  $('#draft-name').value = ''
  wear(user.outfits[0])
})

$('#draft-discard').addEventListener('click', async () => {
  state.user = await api(`/users/${state.user.id}/outfits/_draft`, { method: 'DELETE' })
  wear(state.user.outfits[0] || null)
})

function fillBody() {
  const user = state.user
  $('#body-height').value = Math.round(user.height)
  $('#body-weight').value = Math.round(user.weight)
  document.querySelectorAll('[data-body-shape]').forEach((item) => item.classList.toggle('on', item.dataset.bodyShape === (user.shape || 'average')))
  $('#body-error').textContent = ''
}

let bodyTimer = 0

async function saveBody(patch, preview = true) {
  if (!state.user) return
  Object.assign(state.user, patch)
  if (preview) applyBody()
  clearTimeout(bodyTimer)
  bodyTimer = setTimeout(async () => {
    try {
      $('#body-error').textContent = ''
      state.user = await api(`/users/${state.user.id}`, { method: 'POST', body: JSON.stringify(patch) })
      fillBody()
      applyBody()
    } catch (error) {
      $('#body-error').textContent = error.message
    }
  }, 400)
}

let hairStyles = []

async function renderHair() {
  if (!hairStyles.length) hairStyles = await fetch('/hair/manifest.json').then((response) => response.json()).catch(() => [])
  const list = $('#hair-list')
  list.innerHTML = ''
  for (const style of [{ id: 'none', label: 'None' }, ...hairStyles]) {
    const chip = document.createElement('button')
    chip.type = 'button'
    chip.className = `chip${(state.user.hair || 'none') === style.id ? ' on' : ''}`
    chip.textContent = style.label
    chip.addEventListener('click', async () => {
      state.user = await api(`/users/${state.user.id}`, { method: 'POST', body: JSON.stringify({ hair: style.id }) })
      if (state.pendingLook) state.pendingLook.hair = style.id
      viewer.contentWindow?.postMessage(JSON.stringify({ type: 'hairstyle', id: style.id }), '*')
      renderHair()
    })
    list.append(chip)
  }
}

function selectTab(name) {
  document.querySelectorAll('[data-tab]').forEach((button) => button.classList.toggle('on', button.dataset.tab === name))
  document.querySelectorAll('.tab').forEach((tab) => tab.classList.toggle('on', tab.id === `tab-${name}`))
}

document.querySelectorAll('[data-tab]').forEach((button) => button.addEventListener('click', () => selectTab(button.dataset.tab)))

$('#outfit-build').addEventListener('click', async () => {
  const button = $('#outfit-build')
  $('#outfit-error').textContent = ''
  button.disabled = true
  try {
    await uploadPhotos(state.user.id, 'outfit')
    await api(`/users/${state.user.id}/build?kind=outfit&mirror=${$('#outfit-mirror').checked ? 1 : 0}`, { method: 'POST' })
    state.photos.outfit = {}
    photoSlots('outfit')
    watchBuild('outfit')
  } catch (error) {
    $('#outfit-error').textContent = error.message
  } finally {
    button.disabled = false
  }
})

$('#body-height').addEventListener('input', () => saveBody({ height: Number($('#body-height').value) }))
$('#body-weight').addEventListener('input', () => saveBody({ weight: Number($('#body-weight').value) }))
document.querySelectorAll('[data-body-shape]').forEach((button) => {
  button.addEventListener('click', () => saveBody({ shape: button.dataset.bodyShape }))
})

$('#wear-body').addEventListener('click', () => wear(null))
$('#show-skeleton').addEventListener('change', () => {
  viewer.contentWindow?.postMessage(JSON.stringify({ type: 'skeleton', on: $('#show-skeleton').checked }), '*')
})

$('#switch-user').addEventListener('click', async () => {
  state.users = await api('/users')
  renderUsers()
  show('users')
})

// --- start -----------------------------------------------------------------

async function boot() {
  photoSlots('outfit')
  try {
    state.users = await api('/users')
    const job = await api('/job')
    if (job.busy) {
      state.user = state.users.find((user) => user.id === job.user) || null
      return watchBuild(job.kind)
    }
  } catch (error) {
    show('create')
    photoSlots('create')
    $('#create-error').textContent = error.message
    return
  }
  if (!state.users.length) return startCreate(false)
  const last = localStorage.getItem('dressme.user')
  const known = state.users.find((user) => user.id === last && user.ready)
  if (known) return openUser(known.id)
  if (state.users.length === 1 && state.users[0].ready) return openUser(state.users[0].id)
  renderUsers()
  show('users')
}

boot()
