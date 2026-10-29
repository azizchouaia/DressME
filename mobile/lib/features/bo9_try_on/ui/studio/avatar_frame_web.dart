import 'dart:convert';
import 'dart:js_interop';

import 'package:flutter/material.dart';
import 'package:web/web.dart' as web;

/// Web: Nadhir's Three.js viewer (avatar_studio/web/viewer) served by the API, in an iframe.
/// [outfit] (slot -> {color, long}) is sent to the viewer, which paints the pieces on the body.
class AvatarFrame extends StatefulWidget {
  const AvatarFrame({super.key, required this.url, this.outfit = const {}});

  final String url;
  final Map<String, dynamic> outfit;

  @override
  State<AvatarFrame> createState() => _AvatarFrameState();
}

class _AvatarFrameState extends State<AvatarFrame> {
  web.HTMLIFrameElement? _frame;
  JSFunction? _listener;

  @override
  void initState() {
    super.initState();
    _listener = ((web.Event event) {
      final message = event as web.MessageEvent;
      final data = message.data?.dartify();
      if (data is String && data.contains('"ready"')) {
        Future<void>.delayed(const Duration(milliseconds: 600), _send); // body loads right after "ready"
      }
    }).toJS;
    web.window.addEventListener('message', _listener);
  }

  @override
  void didUpdateWidget(AvatarFrame old) {
    super.didUpdateWidget(old);
    _send();
  }

  @override
  void dispose() {
    final l = _listener;
    if (l != null) web.window.removeEventListener('message', l);
    super.dispose();
  }

  void _send() {
    _frame?.contentWindow?.postMessage(jsonEncode({'type': 'outfit', 'pieces': widget.outfit}).toJS, '*'.toJS);
  }

  @override
  Widget build(BuildContext context) => HtmlElementView.fromTagName(
        key: ValueKey(widget.url),
        tagName: 'iframe',
        onElementCreated: (element) {
          final frame = element as web.HTMLIFrameElement;
          frame.src = widget.url;
          frame.style.border = '0';
          frame.style.width = '100%';
          frame.style.height = '100%';
          frame.allow = 'camera; fullscreen';
          frame.onload = ((web.Event _) {
            Future<void>.delayed(const Duration(milliseconds: 1500), _send);
          }).toJS;
          _frame = frame;
        },
      );
}
