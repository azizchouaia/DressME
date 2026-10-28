import 'package:go_router/go_router.dart';

import 'home_screen.dart';
import 'shell.dart';

import '../core/design/design_gallery_screen.dart';

import '../features/bo1_recommendations/ui/bo1_recommendations_screen.dart';
import '../features/bo2_time/ui/bo2_time_screen.dart';
import '../features/bo3_sustainability/ui/bo3_sustainability_screen.dart';
import '../features/bo4_style/ui/bo4_style_screen.dart';
import '../features/bo5_smart_buy/ui/bo5_smart_buy_screen.dart';
import '../features/bo6_boutique/ui/bo6_boutique_screen.dart';
import '../features/bo6_boutique/ui/bo6_help_screen.dart';
import '../features/bo6_local_market/ui/bo6_local_market_screen.dart';
import '../features/bo7_sharing/ui/bo7_sharing_screen.dart';
import '../features/bo8_assistant/ui/bo8_assistant_screen.dart';
import '../features/bo9_try_on/ui/bo9_try_on_screen.dart';

final router = GoRouter(
  initialLocation: '/',
  routes: [
    ShellRoute(
      builder: (_, state, child) => AppShell(location: state.uri.path, child: child),
      routes: [
    GoRoute(path: '/', builder: (_, __) => const HomeScreen()),
    GoRoute(path: '/bo1_recommendations', builder: (_, __) => const RecommendationsScreen()),
    GoRoute(path: '/bo2_time', builder: (_, __) => const OutfitOfDayScreen()),
    GoRoute(path: '/bo3_sustainability', builder: (_, __) => const InventoryScreen()),
    GoRoute(path: '/bo4_style', builder: (_, __) => const StyleProfileScreen()),
    GoRoute(path: '/bo5_smart_buy', builder: (_, __) => const SmartBuyScreen()),
    GoRoute(path: '/bo6_local_market', builder: (_, __) => const LocalMarketScreen()),
    GoRoute(
        path: '/bo6_boutique',
        builder: (_, state) => BoutiqueScreen(
            initialTab: int.tryParse(state.uri.queryParameters['tab'] ?? '') ?? 0)),
    GoRoute(
        path: '/bo6_boutique/help/:proId/:clientId',
        builder: (_, state) => HelpClientScreen(
            proId: state.pathParameters['proId']!,
            clientId: state.pathParameters['clientId']!,
            handoffId: state.uri.queryParameters['handoff'])),
    GoRoute(path: '/bo7_sharing', builder: (_, __) => const FeedScreen()),
    GoRoute(path: '/bo8_assistant', builder: (_, __) => const ChatScreen()),
    GoRoute(path: '/design', builder: (_, __) => const DesignGalleryScreen()),
    GoRoute(path: '/bo9_try_on', builder: (_, __) => const TryOnScreen()),
      ],
    ),
  ],
);
