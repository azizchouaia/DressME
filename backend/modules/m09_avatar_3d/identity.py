CARD = {
    "name": "tryon",
    "version": "1.0.0",
    "owner": "BO9",
    "module": "M9",
    "role": "Shows an outfit on the faceless 3D avatar from the real body and garment manifest.",
    "rules": ["The body is SMPL-X", "Clothes follow the pose because they are skinned to the body"],
    "when_to_use": ["Show this outfit on me", "Try this piece on the avatar"],
    "when_not_to_use": ["What should I wear? -> stylist", "Should I buy this? -> smartbuy"],
    "skills": {
        "render": "M9 place shirt, shorts, and vest on the SMPL-X body",
        "pose": "M9 tpose, stand, hips, step, or wave",
    },
    "handoff": [{"action": "share", "label": "Share this look", "tool": "share", "args": {}}],
}
