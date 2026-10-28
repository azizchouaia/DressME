import 'dart:convert';
import 'dart:js_interop';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:web/web.dart' as web;

class MeshView extends StatefulWidget {
  const MeshView({super.key, required this.meshUrl, required this.height});

  final String? meshUrl;
  final double height;

  @override
  State<MeshView> createState() => _MeshViewState();
}

class _MeshViewState extends State<MeshView> {
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
        if (decoded is Map && decoded['type'] == 'ready') _send();
      }
    }).toJS;
    web.window.addEventListener('message', _listener);
  }

  @override
  void didUpdateWidget(MeshView oldWidget) {
    super.didUpdateWidget(oldWidget);
    _send();
  }

  @override
  void dispose() {
    final listener = _listener;
    if (listener != null) web.window.removeEventListener('message', listener);
    super.dispose();
  }

  void _send() {
    _frame?.contentWindow?.postMessage(
      jsonEncode({'type': 'scene', 'url': widget.meshUrl ?? '', 'height': widget.height}).toJS,
      '*'.toJS,
    );
  }

  @override
  Widget build(BuildContext context) {
    final src = Uri.base.resolve('viewer/index.html?mesh=/smplx_body.glb&v=49').toString();
    return HtmlElementView.fromTagName(
      tagName: 'iframe',
      onElementCreated: (element) {
        final frame = element as web.HTMLIFrameElement;
        frame.src = src;
        frame.style.border = '0';
        frame.style.width = '100%';
        frame.style.height = '100%';
        _frame = frame;
      },
    );
  }
}

String? createMeshUrl(Uint8List bytes) {
  final blob = web.Blob([bytes.toJS].toJS, web.BlobPropertyBag(type: 'model/gltf-binary'));
  return web.URL.createObjectURL(blob);
}

void revokeMeshUrl(String url) {
  web.URL.revokeObjectURL(url);
}
