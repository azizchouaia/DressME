import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

/// Phones / desktop: the Three.js viewer opens in the browser.
class AvatarFrame extends StatelessWidget {
  const AvatarFrame({super.key, required this.url});

  final String url;

  @override
  Widget build(BuildContext context) => Center(
        child: FilledButton.icon(
          onPressed: () => launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication),
          icon: const Icon(Icons.open_in_new_rounded),
          label: const Text('Open the 3D avatar studio'),
        ),
      );
}
