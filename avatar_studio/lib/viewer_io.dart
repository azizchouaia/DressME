import 'dart:typed_data';

import 'package:flutter/material.dart';

class MeshView extends StatelessWidget {
  const MeshView({super.key, required this.meshUrl, required this.height});

  final String? meshUrl;
  final double height;

  @override
  Widget build(BuildContext context) {
    return const ColoredBox(
      color: Color(0xFFE7E1D8),
      child: Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text(
            'Open Avatar Studio in a browser on this computer to turn the mesh around. Save still writes the GLB.',
            textAlign: TextAlign.center,
          ),
        ),
      ),
    );
  }
}

String? createMeshUrl(Uint8List bytes) => null;

void revokeMeshUrl(String url) {}
