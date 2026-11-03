import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class AppShell extends StatelessWidget {
  const AppShell({super.key, required this.child});

  final Widget child;

  static const _destinations = [
    ('/home', 'Home', Icons.home_outlined),
    ('/wardrobe', 'Wardrobe', Icons.checkroom_outlined),
    ('/outfits', 'Outfits', Icons.layers_outlined),
    ('/avatar', 'Avatar', Icons.accessibility_new_outlined),
    ('/profile', 'Profile', Icons.person_outline),
  ];

  int _index(String location) {
    if (location.startsWith('/wardrobe')) return 1;
    if (location.startsWith('/outfits')) return 2;
    if (location.startsWith('/avatar')) return 3;
    if (location.startsWith('/profile')) return 4;
    return 0;
  }

  @override
  Widget build(BuildContext context) {
    final location = GoRouterState.of(context).uri.path;
    final index = _index(location);
    return Scaffold(
      body: SafeArea(child: child),
      bottomNavigationBar: NavigationBar(
        selectedIndex: index,
        onDestinationSelected: (next) => context.go(_destinations[next].$1),
        destinations: [
          for (final item in _destinations) NavigationDestination(icon: Icon(item.$3), label: item.$2),
        ],
      ),
    );
  }
}
