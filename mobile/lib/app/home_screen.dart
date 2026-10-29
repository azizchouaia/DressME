// Home: every BO in one place + a live check that each BO's backend answers (integration test from the phone).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/api/dm_api.dart';
import '../core/auth/auth.dart';
import '../core/design/dressme_design.dart';
import '../core/widgets/dm_widgets.dart';
import 'today_card.dart';

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
  BoEntry('BO4', 'My style · swipe & learn', 'Amine', '/my_style', Icons.style_outlined, 'M5 · M2',
      (a) => a.get('/m05/styles')),
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
  BoEntry('BO9', 'My 3D avatar', 'Nadhir', '/bo9_avatar', Icons.view_in_ar_outlined, 'SMPL-X studio',
      (a) => a.get('/viewer/index.html')),
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

  int? _pieces; // pieces in the signed-in user's wardrobe (null = loading)

  @override
  void initState() {
    super.initState();
    _loadPieces();
  }

  Future<void> _loadPieces() async {
    try {
      final r = await ref.read(dmApiProvider).post('/m01/items', {'user_id': DemoUsers.wardrobe});
      final res = r['result'] is Map ? r['result'] as Map : r;
      if (mounted) setState(() => _pieces = jsonList(res['items']).length);
    } catch (_) {
      if (mounted) setState(() => _pieces = 0);
    }
  }

  String get _hello {
    final h = DateTime.now().hour;
    return h < 12 ? 'Good morning' : (h < 18 ? 'Good afternoon' : 'Good evening');
  }

  Widget _action(String title, String sub, IconData icon, String route, {bool dark = false}) => Expanded(
        child: _Pressable(
          onTap: () => context.go(route),
          child: Container(
            height: 132,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: dark ? DmColors.inkDeep : Colors.white,
              borderRadius: BorderRadius.circular(DmRadius.panel),
              border: Border.all(color: dark ? DmColors.inkDeep : DmColors.border),
              boxShadow: const [BoxShadow(color: Color(0x0F000000), blurRadius: 12, offset: Offset(0, 4))],
            ),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(color: dark ? DmColors.gold : DmColors.sandDark, borderRadius: BorderRadius.circular(12)),
                child: Icon(icon, size: 20, color: dark ? DmColors.inkDeep : DmColors.bronze),
              ),
              const Spacer(),
              Text(title, style: DmText.cardTitle.copyWith(color: dark ? Colors.white : DmColors.text)),
              const SizedBox(height: 2),
              Text(sub, maxLines: 1, overflow: TextOverflow.ellipsis,
                  style: DmText.caption.copyWith(color: dark ? DmColors.goldLight : DmColors.muted)),
            ]),
          ),
        ),
      );

  Widget _step(int n, String title, String sub, bool done, String route) => ListTile(
        contentPadding: EdgeInsets.zero,
        onTap: () => context.go(route),
        leading: AnimatedContainer(
          duration: const Duration(milliseconds: 300),
          width: 34,
          height: 34,
          decoration: BoxDecoration(color: done ? DmColors.success : DmColors.sandDark, shape: BoxShape.circle),
          child: Center(
            child: done
                ? const Icon(Icons.check_rounded, size: 18, color: Colors.white)
                : Text('$n', style: DmText.body.copyWith(fontWeight: FontWeight.w700, color: DmColors.bronze)),
          ),
        ),
        title: Text(title,
            style: DmText.body.copyWith(
                fontWeight: FontWeight.w700, decoration: done ? TextDecoration.lineThrough : null, color: done ? DmColors.muted : DmColors.text)),
        subtitle: Text(sub, style: DmText.caption),
        trailing: const Icon(Icons.chevron_right_rounded, color: DmColors.muted),
      );

  @override
  Widget build(BuildContext context) {
    final ok = _state.values.where((s) => s == _State.ok).length;
    final ran = _state.values.where((s) => s == _State.ok || s == _State.fail).length;
    final user = ref.watch(authProvider).user;
    final first = (user?.name ?? '').split(' ').first;
    final pieces = _pieces;
    final ready = (pieces ?? 0) >= 2;
    return Scaffold(
      body: RefreshIndicator(
        onRefresh: _loadPieces,
        child: ListView(padding: EdgeInsets.zero, children: [
          DmHero(
            eyebrow: 'DressMe · your digital wardrobe',
            title: '$_hello${first.isEmpty ? '' : ', $first'}',
            trailing: IconButton(
              tooltip: 'My account',
              onPressed: () => context.go('/profile'),
              icon: const Icon(Icons.person_outline_rounded, color: Colors.white),
            ),
            child: AnimatedSwitcher(
              duration: const Duration(milliseconds: 300),
              child: Text(
                key: ValueKey(pieces),
                pieces == null
                    ? 'Opening your wardrobe…'
                    : pieces == 0
                        ? 'Your wardrobe is empty. Add your first piece to start.'
                        : '$pieces piece${pieces == 1 ? '' : 's'} in your wardrobe${ready ? ' · outfits ready' : ' · add one more for outfits'}',
                style: DmText.body.copyWith(color: DmColors.goldLight),
              ),
            ),
          ),
          Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 720),
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 20, 16, 40),
                child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                  // first steps until the wardrobe can make outfits
                  if (pieces != null && !ready) ...[
                    DmCard(
                      big: true,
                      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                        const Text('GET STARTED', style: DmText.eyebrow),
                        const SizedBox(height: 4),
                        const Text('3 steps to your first outfit', style: DmText.cardTitle),
                        const SizedBox(height: 6),
                        _step(1, 'Add 2 pieces', 'A photo is enough: cut out, classified, put away.', pieces >= 2, '/bo4_style'),
                        _step(2, 'Get an outfit', 'Made from your own pieces and the weather.', false, '/bo1_recommendations'),
                        _step(3, 'Check a buy', 'Before paying, see if it fits your wardrobe.', false, '/bo5_smart_buy'),
                      ]),
                    ),
                    const SizedBox(height: 18),
                  ],
                  if (ready) ...[
                    const TodayCard(),
                    const SizedBox(height: 22),
                  ],
                  const Text('WHAT DO YOU NEED?', style: DmText.eyebrow),
                  const SizedBox(height: 10),
                  Row(children: [
                    _action("Today's outfit", 'Ready in one tap', Icons.wb_sunny_outlined, '/bo2_time', dark: true),
                    const SizedBox(width: 12),
                    _action('My style', 'Swipe, it learns your taste', Icons.style_outlined, '/my_style'),
                  ]),
                  const SizedBox(height: 12),
                  Row(children: [
                    _action('Should I buy it?', 'Smart Buy', Icons.shopping_bag_outlined, '/bo5_smart_buy'),
                    const SizedBox(width: 12),
                    _action('Ask DressMe', 'Your style assistant', Icons.chat_bubble_outline_rounded, '/bo8_assistant'),
                  ]),
                  const SizedBox(height: 24),
                  const Text('EXPLORE', style: DmText.eyebrow),
                  const SizedBox(height: 10),
                  for (final b in boEntries)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: DmCard(
                        onTap: () => context.go(b.route),
                        child: Row(children: [
                          Container(
                            width: 42,
                            height: 42,
                            decoration: const BoxDecoration(color: DmColors.sandDark, shape: BoxShape.circle),
                            child: Icon(b.icon, color: DmColors.bronze, size: 20),
                          ),
                          const SizedBox(width: 12),
                          Expanded(child: Text(b.title, style: DmText.cardTitle)),
                          const Icon(Icons.chevron_right_rounded, color: DmColors.muted),
                        ]),
                      ),
                    ),
                  const SizedBox(height: 16),
                  // the integration check stays, folded away for the team
                  DmCard(
                    child: Theme(
                      data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
                      child: ExpansionTile(
                        tilePadding: EdgeInsets.zero,
                        leading: const Icon(Icons.science_outlined, color: DmColors.bronze),
                        title: const Text('For the team · test every BO', style: DmText.cardTitle),
                        subtitle: Text(ran == 0 ? 'Server: ${apiBaseUrl()}' : '$ok / ${boEntries.length} BOs answering',
                            style: DmText.caption),
                        children: [
                          Align(
                            alignment: Alignment.centerLeft,
                            child: DmButton('Test all BOs', kind: DmButtonKind.gold, icon: Icons.play_arrow_rounded, onPressed: _checkAll),
                          ),
                          const SizedBox(height: 8),
                          for (final b in boEntries)
                            ListTile(
                              contentPadding: EdgeInsets.zero,
                              dense: true,
                              title: Text('${b.code} · ${b.title}', style: DmText.body),
                              subtitle: Text(
                                  _state[b.route] == _State.fail ? (_error[b.route] ?? '') : '${b.owner} · ${b.modules}',
                                  maxLines: 2,
                                  style: DmText.caption.copyWith(color: _state[b.route] == _State.fail ? DmColors.warning : null)),
                              trailing: _Status(state: _state[b.route] ?? _State.idle, onTap: () => _check(b)),
                            ),
                        ],
                      ),
                    ),
                  ),
                ]),
              ),
            ),
          ),
        ]),
      ),
    );
  }
}

/// A card that shrinks a little under the finger.
class _Pressable extends StatefulWidget {
  const _Pressable({required this.child, required this.onTap});

  final Widget child;
  final VoidCallback onTap;

  @override
  State<_Pressable> createState() => _PressableState();
}

class _PressableState extends State<_Pressable> {
  bool down = false;

  @override
  Widget build(BuildContext context) => MouseRegion(
        cursor: SystemMouseCursors.click,
        child: GestureDetector(
          onTapDown: (_) => setState(() => down = true),
          onTapCancel: () => setState(() => down = false),
          onTapUp: (_) => setState(() => down = false),
          onTap: widget.onTap,
          child: AnimatedScale(scale: down ? .97 : 1, duration: const Duration(milliseconds: 120), child: widget.child),
        ),
      );
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
