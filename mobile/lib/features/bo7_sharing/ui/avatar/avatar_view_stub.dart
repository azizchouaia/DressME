// Owner: BO7 — Android / iOS version of the avatar view (no embedded web page here).
import 'package:flutter/material.dart';

import '../../../../core/design/dressme_design.dart';

/// False here: the 3D viewer of BO9 is a web page, shown only in the web version of the app.
const bool avatarViewerSupported = false;

class AvatarViewController {
  /// PNG data URI of the avatar as shown, or null when it cannot be taken.
  Future<String?> capture() async => null;
}

class AvatarView extends StatelessWidget {
  const AvatarView({super.key, required this.url, required this.controller});

  final String url;
  final AvatarViewController controller;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(color: DmColors.sand, borderRadius: BorderRadius.circular(DmRadius.hero)),
      padding: const EdgeInsets.all(24),
      child: const Center(
        child: Text(
          'L\'avatar 3D de BO9 s\'affiche dans la version web de l\'app (navigateur). '
          'Sur téléphone, importe une capture de ton avatar.',
          textAlign: TextAlign.center,
          style: DmText.body,
        ),
      ),
    );
  }
}
