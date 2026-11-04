// Home "Your month": how the wardrobe is used (M3, BO3) and what Smart Buy saved (M6, BO5), in 4 tiles.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/api/dm_api.dart';
import '../core/design/dressme_design.dart';
import '../core/widgets/dm_motion.dart';

class WeekCard extends ConsumerStatefulWidget {
  const WeekCard({super.key});

  @override
  ConsumerState<WeekCard> createState() => _WeekCardState();
}

class _WeekCardState extends ConsumerState<WeekCard> {
  Json? stats;
  List<Json> history = const [];
  bool loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final api = ref.read(dmApiProvider);
    try {
      stats = await api.call('/m03/stats', userId: DemoUsers.outfits);
    } catch (_) {}
    try {
      history = jsonList((await api.get('/m06/history/${DemoUsers.wardrobe}', query: {'n': 50}))['history']);
    } catch (_) {}
    if (mounted) setState(() => loading = false);
  }

  @override
  Widget build(BuildContext context) {
    final s = (stats?['summary'] as Map?)?.cast<String, dynamic>() ?? const {};
    final cutoff = DateTime.now().subtract(const Duration(days: 30));
    final recent = history.where((h) => (DateTime.tryParse('${h['at']}'.replaceFirst(' ', 'T')) ?? DateTime(2000)).isAfter(cutoff)).toList();
    final skipped = recent.where((h) => h['verdict'] == 'skip').toList();
    final saved = skipped.fold<num>(0, (a, h) => a + ((h['price_tnd'] as num?) ?? 0));
    final used = (s['utilisation_30d'] as num?)?.toDouble();
    final forgotten = (s['forgotten_60d'] as List?)?.length ?? 0;
    final logged = (s['outfits_logged'] as num?)?.toInt() ?? 0;

    Widget tile(String value, String label, IconData icon, String route, {Color? accent}) => Expanded(
          child: DmPressable(
            onTap: () {},
            child: InkWell(
              borderRadius: BorderRadius.circular(DmRadius.card),
              onTap: () => context.go(route),
              child: Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: DmColors.page,
                  borderRadius: BorderRadius.circular(DmRadius.card),
                  border: Border.all(color: DmColors.border),
                ),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Icon(icon, size: 18, color: accent ?? DmColors.bronze),
                  const SizedBox(height: 8),
                  FittedBox(
                    fit: BoxFit.scaleDown,
                    alignment: Alignment.centerLeft,
                    child: Text(value, style: DmText.title.copyWith(fontSize: 22, color: accent)),
                  ),
                  Text(label, style: DmText.caption, maxLines: 2, overflow: TextOverflow.ellipsis),
                ]),
              ),
            ),
          ),
        );

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(DmRadius.panel),
        border: Border.all(color: DmColors.border),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const Row(children: [
          Text('YOUR LAST 30 DAYS', style: DmText.eyebrow),
          Spacer(),
          Icon(Icons.insights_outlined, size: 18, color: DmColors.bronze),
        ]),
        const SizedBox(height: 12),
        if (loading)
          const Row(children: [
            Expanded(child: DmShimmer(height: 86)),
            SizedBox(width: 8),
            Expanded(child: DmShimmer(height: 86)),
          ])
        else ...[
          Row(children: [
            tile(used == null ? '–' : '${(used * 100).round()} %', 'of your pieces worn', Icons.checkroom, '/bo3_sustainability',
                accent: DmColors.eco),
            const SizedBox(width: 8),
            tile('$logged', 'outfits logged', Icons.event_available_outlined, '/bo3_sustainability'),
          ]),
          const SizedBox(height: 8),
          Row(children: [
            tile('$forgotten', forgotten == 1 ? 'forgotten piece to wear again' : 'forgotten pieces to wear again',
                Icons.history_rounded, '/bo3_sustainability', accent: forgotten > 0 ? DmColors.warning : null),
            const SizedBox(width: 8),
            tile('${saved.round()} TND', skipped.isEmpty ? 'saved by Smart Buy (no SKIP yet)' : 'not spent: ${skipped.length} SKIP verdict(s)',
                Icons.savings_outlined, '/bo5_smart_buy', accent: DmColors.success),
          ]),
        ],
      ]),
    );
  }
}
