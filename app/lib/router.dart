import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'screens/add_clothing_page.dart';
import 'screens/auth_page.dart';
import 'screens/avatar_studio_page.dart';
import 'screens/clothing_detail_page.dart';
import 'screens/home_page.dart';
import 'screens/outfits_page.dart';
import 'screens/profile_page.dart';
import 'screens/shell.dart';
import 'screens/wardrobe_page.dart';
import 'screens/welcome_page.dart';
import 'state.dart';
import 'theme.dart';

final routerProvider = Provider<GoRouter>((ref) {
  final refresh = ValueNotifier<int>(0);
  ref.onDispose(refresh.dispose);
  ref.listen(authProvider, (_, _) => refresh.value++);

  return GoRouter(
    initialLocation: '/welcome',
    refreshListenable: refresh,
    redirect: (context, state) {
      final signedIn = ref.read(authProvider) != null;
      final path = state.matchedLocation;
      final public = path == '/welcome' || path == '/login' || path == '/register';
      if (!signedIn && !public) return '/welcome';
      if (signedIn && public) return '/home';
      return null;
    },
    routes: [
      GoRoute(path: '/welcome', builder: (_, _) => const WelcomePage()),
      GoRoute(path: '/login', builder: (_, _) => const AuthPage(register: false)),
      GoRoute(path: '/register', builder: (_, _) => const AuthPage(register: true)),
      ShellRoute(
        builder: (_, _, child) => AppShell(child: child),
        routes: [
          GoRoute(path: '/home', builder: (_, _) => const HomePage()),
          GoRoute(
            path: '/wardrobe',
            builder: (_, _) => const WardrobePage(),
            routes: [
              GoRoute(path: 'add', builder: (_, _) => const AddClothingPage()),
              GoRoute(
                path: ':id',
                builder: (_, state) => ClothingDetailPage(id: state.pathParameters['id']!),
              ),
            ],
          ),
          GoRoute(path: '/outfits', builder: (_, _) => const OutfitsPage()),
          GoRoute(path: '/avatar', builder: (_, _) => const AvatarStudioPage()),
          GoRoute(path: '/profile', builder: (_, _) => const ProfilePage()),
        ],
      ),
    ],
  );
});

class SmartWardrobeApp extends ConsumerWidget {
  const SmartWardrobeApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp.router(title: 'Smart Wardrobe', theme: buildTheme(), routerConfig: ref.watch(routerProvider));
  }
}
