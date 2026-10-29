// App shell: bottom navigation shared by every screen. "More" opens the BOs that are not in the bar.
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../core/design/dressme_design.dart';

class _Tab {
  const _Tab(this.label, this.icon, this.route, [this.also = const []]);

  final String label;
  final IconData icon;
  final String route;
  final List<String> also; // other routes that light this tab
}

const _tabs = [
  _Tab('Home', Icons.home_outlined, '/'),
  _Tab('Wardrobe', Icons.checkroom, '/bo4_style', ['/bo3_sustainability', '/my_style']),
  _Tab('Outfits', Icons.auto_awesome, '/bo1_recommendations', ['/bo2_time', '/bo9_try_on', '/bo9_avatar']),
  _Tab('Shop', Icons.shopping_bag_outlined, '/bo5_smart_buy', ['/bo6_local_market', '/bo6_boutique']),
  _Tab('Assistant', Icons.chat_bubble_outline_rounded, '/bo8_assistant'),
  _Tab('More', Icons.grid_view_rounded, '/bo7_sharing', ['/design', '/profile']),
];

const _more = [
  ('BO2 · Ready in one tap', '/bo2_time', Icons.wb_sunny_outlined),
  ('BO4 · My style (swipe)', '/my_style', Icons.style_outlined),
  ('BO3 · Wear what you own', '/bo3_sustainability', Icons.eco_outlined),
  ('BO6 · Local shops', '/bo6_local_market', Icons.storefront_outlined),
  ('BO6 · Boutique', '/bo6_boutique', Icons.store_mall_directory_outlined),
  ('BO7 · Share & challenges', '/bo7_sharing', Icons.groups_2_outlined),
  ('BO9 · My 3D avatar', '/bo9_avatar', Icons.view_in_ar_outlined),
  ('BO9 · Try it on', '/bo9_try_on', Icons.accessibility_new_rounded),
  ('Design kit', '/design', Icons.palette_outlined),
  ('My account', '/profile', Icons.person_outline_rounded),
];

class AppShell extends StatelessWidget {
  const AppShell({super.key, required this.location, required this.child});

  final String location;
  final Widget child;

  int get _index {
    final i = _tabs.indexWhere((t) => t.route == '/' ? location == '/' : (location.startsWith(t.route) || t.also.any(location.startsWith)));
    return i < 0 ? 0 : i;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: AnimatedSwitcher( // soft fade + rise between screens
        duration: const Duration(milliseconds: 260),
        switchInCurve: Curves.easeOutCubic,
        transitionBuilder: (w, a) => FadeTransition(
          opacity: a,
          child: SlideTransition(position: Tween(begin: const Offset(0, .015), end: Offset.zero).animate(a), child: w),
        ),
        child: KeyedSubtree(key: ValueKey(location), child: child),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        backgroundColor: DmColors.surface,
        indicatorColor: DmColors.sandDark,
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
        destinations: [for (final t in _tabs) NavigationDestination(icon: Icon(t.icon), label: t.label)],
        onDestinationSelected: (i) {
          if (_tabs[i].label == 'More') {
            _showMore(context);
          } else {
            context.go(_tabs[i].route);
          }
        },
      ),
    );
  }

  void _showMore(BuildContext context) {
    showModalBottomSheet<void>(
      context: context,
      builder: (sheet) => SafeArea(
        child: ListView(shrinkWrap: true, padding: const EdgeInsets.symmetric(vertical: 12), children: [
          for (final (label, route, icon) in _more)
            ListTile(
              leading: Icon(icon, color: DmColors.bronze),
              title: Text(label),
              onTap: () {
                Navigator.pop(sheet);
                context.go(route);
              },
            ),
        ]),
      ),
    );
  }
}
