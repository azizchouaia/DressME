# BO9 · Virtual try-on 3D

The body creator for this objective is on `feat/bo9-avatar-3d`.

- Viewer and Flutter shell: `avatar_studio/` (start with `avatar_studio/README.md`)
- SMPL-X export and the local photo server: `ai/`

The screen shows one Build slider (thin to heavy), body details behind one icon, and gender plus photos behind an Avatar icon. Pose work is kept in the viewer and is not opened from the screen. Official SMPL-X files and generated GLBs are not in git.

**Business objective:** Differentiate & convert · **Owner:** @bo9-owner

**Shared modules owned:** M9 3D avatar renderer

**Shared modules called:** M1, M2, M5, M7, M8, M9, M10, M13, M18 (mock them until they are ready)

## Own tasks
| Task | Calls |
|---|---|
    | Drag-and-drop builder on the avatar | M2, M9 |
| Try a photographed piece | M1, M9 |
| Visual explanation on the avatar | M8 |
| Local boutique pieces on the avatar | M7 |
| Try-on reactions -> style profile | M5 |
| 2D diffusion try-on (fallback) | - |
| Avatar estimated from a photo | M9 |
| Size & fit suggestion | M18 |
| Buy link from the try-on view | M13 |
| Partner promo code after try-on | M13 |
| Share the try-on look | M10 |
