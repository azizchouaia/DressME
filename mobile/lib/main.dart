import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app/router.dart';
import 'app/theme.dart';

void main() {
  runApp(const ProviderScope(child: DressMeApp()));
}

class DressMeApp extends StatelessWidget {
  const DressMeApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'DressMe',
      theme: appTheme,
      routerConfig: router,
    );
  }
}
