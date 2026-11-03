import 'dart:convert';
import 'dart:js_interop';

import 'package:flutter/material.dart';
import 'package:web/web.dart' as web;

import '../config.dart';
import 'viewer_scene.dart';

class AvatarStage extends StatefulWidget {
  const AvatarStage({super.key, required this.scene});

  final ViewerScene scene;

  @override
  State<AvatarStage> createState() => _AvatarStageState();
}

class _AvatarStageState extends State<AvatarStage> {
  web.HTMLIFrameElement? _frame;
  JSFunction? _listener;

  @override
  void initState() {
    super.initState();
    _listener = ((web.Event event) {
      final message = event as web.MessageEvent;
      if (_frame?.contentWindow != null && message.source != _frame!.contentWindow) return;
      final data = message.data?.dartify();
      if (data is String) {
        final decoded = jsonDecode(data);
        if (decoded is Map && decoded['type'] == 'ready') _send(widget.scene);
      }
    }).toJS;
    web.window.addEventListener('message', _listener);
  }

  @override
  void didUpdateWidget(AvatarStage oldWidget) {
    super.didUpdateWidget(oldWidget);
    _send(widget.scene);
  }

  @override
  void dispose() {
    final listener = _listener;
    if (listener != null) web.window.removeEventListener('message', listener);
    super.dispose();
  }

  void _send(ViewerScene scene) {
    _frame?.contentWindow?.postMessage(jsonEncode(scene.toMessage()).toJS, '*'.toJS);
  }

  @override
  Widget build(BuildContext context) {
    final origin = apiOrigin.endsWith('/') ? apiOrigin.substring(0, apiOrigin.length - 1) : apiOrigin;
    return HtmlElementView.fromTagName(
      tagName: 'iframe',
      onElementCreated: (element) {
        final frame = element as web.HTMLIFrameElement;
        frame.src = '$origin/viewer/';
        frame.style.border = '0';
        frame.style.width = '100%';
        frame.style.height = '100%';
        _frame = frame;
      },
    );
  }
}
