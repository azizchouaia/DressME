import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';

import '../config.dart';
import '../theme.dart';
import 'viewer_scene.dart';

class AvatarStage extends StatefulWidget {
  const AvatarStage({super.key, required this.scene});

  final ViewerScene scene;

  @override
  State<AvatarStage> createState() => _AvatarStageState();
}

class _AvatarStageState extends State<AvatarStage> {
  WebViewController? _controller;

  bool get _testMode => Platform.environment['FLUTTER_TEST'] == 'true';

  @override
  void initState() {
    super.initState();
    if (_testMode) return;
    final origin = apiOrigin.endsWith('/') ? apiOrigin.substring(0, apiOrigin.length - 1) : apiOrigin;
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(const Color(0x00000000))
      ..addJavaScriptChannel(
        'FlutterChannel',
        onMessageReceived: (message) {
          final decoded = jsonDecode(message.message);
          if (decoded is Map && decoded['type'] == 'ready') _send(widget.scene);
        },
      )
      ..setNavigationDelegate(NavigationDelegate(onPageFinished: (_) => _send(widget.scene)))
      ..loadRequest(Uri.parse('$origin/viewer/'));
  }

  @override
  void didUpdateWidget(AvatarStage oldWidget) {
    super.didUpdateWidget(oldWidget);
    _send(widget.scene);
  }

  void _send(ViewerScene scene) {
    final payload = jsonEncode(scene.toMessage());
    _controller?.runJavaScript('window.__applyScene($payload)');
  }

  @override
  Widget build(BuildContext context) {
    if (_testMode || _controller == null) {
      return const ColoredBox(color: Color(0xFFE6E0D6));
    }
    return ColoredBox(color: paper, child: WebViewWidget(controller: _controller!));
  }
}
