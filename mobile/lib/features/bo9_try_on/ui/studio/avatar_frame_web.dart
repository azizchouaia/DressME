import 'package:flutter/material.dart';
import 'package:web/web.dart' as web;

/// Web: Nadhir's Three.js viewer (avatar_studio/web/viewer) served by the API, in an iframe.
class AvatarFrame extends StatelessWidget {
  const AvatarFrame({super.key, required this.url});

  final String url;

  @override
  Widget build(BuildContext context) => HtmlElementView.fromTagName(
        key: ValueKey(url),
        tagName: 'iframe',
        onElementCreated: (element) {
          final frame = element as web.HTMLIFrameElement;
          frame.src = url;
          frame.style.border = '0';
          frame.style.width = '100%';
          frame.style.height = '100%';
          frame.allow = 'camera; fullscreen';
        },
      );
}
