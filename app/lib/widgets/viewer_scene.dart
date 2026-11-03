class ViewerScene {
  const ViewerScene.avatar({
    required this.avatarUrl,
    required this.scaleX,
    required this.scaleY,
    required this.scaleZ,
    required this.garments,
    this.shape = const {},
    this.interactive = true,
  }) : mode = 'avatar',
       meshUrl = null;

  const ViewerScene.mesh(this.meshUrl)
    : mode = 'mesh',
      avatarUrl = '',
      scaleX = 1,
      scaleY = 1,
      scaleZ = 1,
      garments = const {},
      shape = const {},
      interactive = true;

  final String mode;
  final String avatarUrl;
  final String? meshUrl;
  final double scaleX;
  final double scaleY;
  final double scaleZ;
  final Map<String, String?> garments;
  final Map<String, double> shape;
  final bool interactive;

  Map<String, dynamic> toMessage() {
    if (mode == 'mesh') return {'type': 'scene', 'mode': 'mesh', 'url': meshUrl};
    return {
      'type': 'scene',
      'mode': 'avatar',
      'avatarUrl': avatarUrl,
      'scale': {'x': scaleX, 'y': scaleY, 'z': scaleZ},
      'shape': shape,
      'garments': garments,
      'interactive': interactive,
    };
  }
}
