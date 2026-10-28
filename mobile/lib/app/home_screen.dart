// Home: every BO in one place + a live check that each BO's backend answers (integration test from the phone).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/api/dm_api.dart';
import '../core/auth/auth.dart';
import '../core/design/dressme_design.dart';
import '../core/widgets/dm_widgets.dart';

class BoEntry {
  const BoEntry(this.code, this.title, this.owner, this.route, this.icon, this.modules, this.check);

  final String code;
  final String title;
  final String owner;
  final String route;
  final IconData icon;
  final String modules;
  final Future<Object?> Function(DmApi api) check; // throws when the BO's backend does not answer
}

final boEntries = <BoEntry>[
  BoEntry('BO1', 'Outfits for you', 'Racem', '/bo1_recommendations', Icons.auto_awesome, 'M2 · M3',
      (a) => a.call('/m02/recommend', userId: DemoUsers.outfits, payload: {'context': {'occasion': 'casual'}})),
  BoEntry('BO2', 'Ready in one tap', 'Racem', '/bo2_time', Icons.wb_sunny_outlined, 'M4 · M17',
      (a) => a.call('/m04/today', userId: DemoUsers.outfits)),
  BoEntry('BO3', 'Wear what you own', 'Amine', '/bo3_sustainability', Icons.eco_outlined, 'M3 · M1',
      (a) => a.call('/m03/stats', userId: DemoUsers.outfits)),
  BoEntry('BO4', 'My wardrobe & style', 'Amine', '/bo4_style', Icons.checkroom, 'M1 · M5',
      (a) => a.post('/m01/items', {'user_id': DemoUsers.wardrobe})),
  BoEntry('BO5', 'Smart Buy', 'Aziz', '/bo5_smart_buy', Icons.shopping_bag_outlined, 'M6 · M13 · M18',
      (a) => a.get('/m06/meta')),
  BoEntry('BO6', 'Local shops', 'Kenza', '/bo6_local_market', Icons.storefront_outlined, 'M7 · M14',
      (a) => a.get('/m07/shops')),
  BoEntry('BO6', 'Boutique (stylists & shops)', 'Kenza', '/bo6_boutique', Icons.store_mall_directory_outlined, 'M14',
      (a) => a.get('/m14/pro')),
  BoEntry('BO7', 'Share & challenges', 'Amenallah', '/bo7_sharing', Icons.groups_2_outlined, 'M10 · M15',
      (a) => a.get('/m15/challenges', query: {'user_id': DemoUsers.wardrobe})),
  BoEntry('BO8', 'Assistant', 'Nadhir', '/bo8_assistant', Icons.chat_bubble_outline_rounded, 'Orchestrator · M8 · M19 · M20',
      (a) => a.get('/chat/agents')),
  BoEntry('BO9', 'Try it on', 'Nadhir', '/bo9_try_on', Icons.accessibility_new_rounded, 'M9',
      (a) => a.get('/m09/options')),
];

enum _State { idle, running, ok, fail }

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  final _state = <String, _State>{}; // key = route (BO6 has two screens)
  final _error = <String, String>{};

  Future<void> _check(BoEntry b) async {
    setState(() => _state[b.route] = _State.running);
    try {
      await b.check(ref.read(dmApiProvider));
      if (mounted) setState(() => _state[b.route] = _State.ok);
    } catch (e) {
      if (mounted) {
        setState(() {
          _state[b.route] = _State.fail;
          _error[b.route] = apiError(e);
        });
      }
    }
  }

  /// One BO after the other: the first calls load AI models (FashionCLIP...), so a burst of
  /// parallel calls makes the single dev server look down.
  Future<void> _checkAll() async {
    for (final b in boEntries) {
      await _check(b);
    }
  }

  @override
  Widget build(BuildContext context) {
    final ok = _state.values.where((s) => s == _State.ok).length;
    final ran = _state.values.where((s) => s == _State.ok || s == _State.fail).length;
    return Scaffold(
      body: ListView(padding: EdgeInsets.zero, children: [
        DmHero(
          eyebrow: 'DressMe · your digital wardrobe',
          title: 'Hello ${ref.watch(authProvider).user?.name.split(' ').first ?? ''} 👋',
          trailing: IconButton(
            tooltip: 'My account',
            onPressed: () => context.go('/profile'),
            icon: const Icon(Icons.person_outline_rounded, color: Colors.white),
          ),
          child: Row(children: [
            Expanded(
              child: Text(ran == 0 ? 'Server: ${apiBaseUrl()}' : '$ok / ${boEntries.length} BOs answering',
                  style: DmText.body.copyWith(color: DmColors.goldLight)),
            ),
            DmButton('Test all BOs', kind: DmButtonKind.gold, icon: Icons.play_arrow_rounded, onPressed: _checkAll),
          ]),
        ),
        Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 720),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 20, 16, 40),
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                for (final b in boEntries)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: DmCard(
                      onTap: () => context.go(b.route),
                      child: Row(children: [
                        Container(
                          width: 46,
                          height: 46,
                          decoration: const BoxDecoration(color: DmColors.sandDark, shape: BoxShape.circle),
                          child: Icon(b.icon, color: DmColors.bronze),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            Text('${b.code} · ${b.title}', style: DmText.cardTitle),
                            Text('${b.owner} · ${b.modules}', style: DmText.caption),
                            if (_state[b.route] == _State.fail)
                              Text(_error[b.route] ?? '', style: DmText.caption.copyWith(color: DmColors.warning), maxLines: 2),
                          ]),
                        ),
                        _Status(state: _state[b.route] ?? _State.idle, onTap: () => _check(b)),
                      ]),
                    ),
                  ),
              ]),
            ),
          ),
        ),
      ]),
    );
  }
}

class _Status extends StatelessWidget {
  const _Status({required this.state, required this.onTap});

  final _State state;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return switch (state) {
      _State.running => const SizedBox(width: 24, height: 24, child: CircularProgressIndicator(strokeWidth: 2)),
      _State.ok => const Icon(Icons.check_circle_rounded, color: DmColors.success),
      _State.fail => IconButton(onPressed: onTap, icon: const Icon(Icons.error_outline_rounded, color: DmColors.warning)),
      _State.idle => IconButton(onPressed: onTap, tooltip: 'Check', icon: const Icon(Icons.play_circle_outline, color: DmColors.muted)),
    };
  }
}
