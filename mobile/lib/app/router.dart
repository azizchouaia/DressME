import 'package:go_router/go_router.dart';

import '../features/onboarding/ui/onboarding_screen.dart';
import '../features/wardrobe/ui/wardrobe_screen.dart';
import '../features/outfit_of_day/ui/outfit_of_day_screen.dart';
import '../features/builder/ui/builder_screen.dart';
import '../features/chat/ui/chat_screen.dart';
import '../features/smart_buy/ui/smart_buy_screen.dart';
import '../features/try_on/ui/try_on_screen.dart';
import '../features/profile/ui/profile_screen.dart';

final router = GoRouter(
  initialLocation: '/outfit_of_day',
  routes: [
    GoRoute(path: '/onboarding', builder: (_, __) => const OnboardingScreen()),
    GoRoute(path: '/wardrobe', builder: (_, __) => const WardrobeScreen()),
    GoRoute(path: '/outfit_of_day', builder: (_, __) => const OutfitOfDayScreen()),
    GoRoute(path: '/builder', builder: (_, __) => const BuilderScreen()),
    GoRoute(path: '/chat', builder: (_, __) => const ChatScreen()),
    GoRoute(path: '/smart_buy', builder: (_, __) => const SmartBuyScreen()),
    GoRoute(path: '/try_on', builder: (_, __) => const TryOnScreen()),
    GoRoute(path: '/profile', builder: (_, __) => const ProfileScreen()),
  ],
);
