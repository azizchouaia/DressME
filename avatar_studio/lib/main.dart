import 'package:flutter/material.dart';

import 'viewer.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized().ensureSemantics();
  runApp(const AvatarStudioApp());
}

class AvatarStudioApp extends StatelessWidget {
  const AvatarStudioApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Avatar Studio',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        scaffoldBackgroundColor: const Color(0xFFF6F4F0),
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF141414), brightness: Brightness.light),
      ),
      home: const Scaffold(
        backgroundColor: Color(0xFFF6F4F0),
        body: MeshView(meshUrl: null, height: 1),
      ),
    );
  }
}
