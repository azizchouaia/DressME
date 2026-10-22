// Owner: BO7 — web version of the avatar view: BO9's Three.js viewer in an iframe (same origin as the API).
// The picture is asked with a message {type: "bo7-snapshot"}; the page served by /bo7/avatar/viewer/ answers
// with a PNG data URI of its canvas (see backend/bo/bo7_sharing/avatar.py).
import 'dart:async';
import 'dart:convert';
import 'dart:js_interop';

import 'package:flutter/material.dart';
import 'package:web/web.dart' as web;

const bool avatarViewerSupported = true;

class AvatarViewController {
  web.HTMLIFrameElement? _frame;
  Completer<String?>? _pending;

  /// PNG data URI of the avatar as shown, or null (no body in the viewer, no answer after 4 s).
  Future<String?> capture() {
    final win = _frame?.contentWindow;
    if (win == null) return Future.value(null);
    final done = Completer<String?>();
    _pending = done;
    win.postMessage(jsonEncode({'type': 'bo7-snapshot'}).toJS, '*'.toJS);
    return done.future.timeout(const Duration(seconds: 8), onTimeout: () => null);
  }

  void _onMessage(String data) {
    Object? decoded;
    try {
      decoded = jsonDecode(data);
    } on FormatException {
      return;
    }
    if (decoded is! Map || decoded['type'] != 'bo7-snapshot') return;
    final png = decoded['png'];
    final pending = _pending;
    _pending = null;
    if (pending != null && !pending.isCompleted) {
      pending.complete(png is String && png.length > 'data:image/png;base64,'.length ? png : null);
    }
  }
}

class AvatarView extends StatefulWidget {
  const AvatarView({super.key, required this.url, required this.controller});

  final String url;
  final AvatarViewController controller;

  @override
  State<AvatarView> createState() => _AvatarViewState();
}

class _AvatarViewState extends State<AvatarView> {
  JSFunction? _listener;

  @override
  void initState() {
    super.initState();
    _listener = ((web.Event event) {
      final message = event as web.MessageEvent;
      final frame = widget.controller._frame;
      if (frame?.contentWindow != null && message.source != frame!.contentWindow) return;
      final data = message.data?.dartify();
      if (data is String) widget.controller._onMessage(data);
    }).toJS;
    web.window.addEventListener('message', _listener);
  }

  @override
  void dispose() {
    final listener = _listener;
    if (listener != null) web.window.removeEventListener('message', listener);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(28),
      child: HtmlElementView.fromTagName(
        tagName: 'iframe',
        onElementCreated: (element) {
          final frame = element as web.HTMLIFrameElement;
          frame.src = widget.url;
          frame.style.border = '0';
          frame.style.width = '100%';
          frame.style.height = '100%';
          widget.controller._frame = frame;
        },
      ),
    );
  }
}
