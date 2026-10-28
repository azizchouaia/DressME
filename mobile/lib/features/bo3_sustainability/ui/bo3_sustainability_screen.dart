// Owner: BO3 (Amine) — wear what you own: usage (M3), forgotten pieces, laundry, duplicates (M1). Integration screen.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/dm_api.dart';
import '../../../core/design/dressme_design.dart';
import '../../../core/widgets/dm_async.dart';
import '../../../core/widgets/dm_widgets.dart';

class InventoryScreen extends ConsumerStatefulWidget {
  const InventoryScreen({super.key});

  @override
  ConsumerState<InventoryScreen> createState() => _InventoryScreenState();
}

class _InventoryScreenState extends ConsumerState<InventoryScreen> {
  int _run = 0;

  DmApi get _api => ref.read(dmApiProvider);

  Future<void> _backInCloset(List ids) async {
    try {
      await _api.call('/m03/laundry_done', userId: DemoUsers.outfits, payload: {'item_ids': ids});
      if (mounted) {
        dmToast(context, 'Back in the closet');
        setState(() => _run++);
      }
    } catch (e) {
      if (mounted) dmToast(context, apiError(e));
    }
  }

  @override
  Widget build(BuildContext context) {
    return DmPage(
      eyebrow: 'BO3 · Wear what you own',
      title: 'My wardrobe use',
      children: [
        DmLoad(
          key: ValueKey('stats-$_run'),
          load: () => _api.call('/m03/stats', userId: DemoUsers.outfits),
          builder: (d, _) {
            final s = (d['summary'] as Map? ?? const {}).cast<String, dynamic>();
            final laundry = (s['in_laundry'] as List? ?? const []);
            return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              DmCard(
                big: true,
                padding: const EdgeInsets.all(18),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Row(children: [
                    const Expanded(child: Text('Last 30 days', style: DmText.title)),
                    DmSource(mocked: d['_mocked'] == true, label: 'M3'),
                  ]),
                  const SizedBox(height: 12),
                  Row(children: [
                    _Stat(value: pct(s['utilisation_30d']), label: 'of your pieces worn'),
                    _Stat(value: '${s['outfits_logged'] ?? 0}', label: 'outfits logged'),
                    _Stat(value: '${(s['forgotten_60d'] as List?)?.length ?? 0}', label: 'forgotten 60 days'),
                  ]),
                  const SizedBox(height: 12),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(6),
                    child: LinearProgressIndicator(
                      value: (s['utilisation_30d'] as num?)?.toDouble() ?? 0,
                      minHeight: 10,
                      color: DmColors.eco,
                      backgroundColor: DmColors.sand,
                    ),
                  ),
                ]),
              ),
              if (laundry.isNotEmpty) ...[
                const SizedBox(height: 12),
                DmCard(
                  child: Row(children: [
                    const Icon(Icons.local_laundry_service_outlined, color: DmColors.bronze),
                    const SizedBox(width: 10),
                    Expanded(child: Text('${laundry.length} piece(s) in the laundry: ${laundry.join(', ')}', style: DmText.body)),
                    TextButton(onPressed: () => _backInCloset(laundry), child: const Text('Back in closet')),
                  ]),
                ),
              ],
              const SizedBox(height: 16),
              const DmSectionHeader(eyebrow: 'Piece by piece', title: 'How often you wear them'),
              const SizedBox(height: 8),
              for (final it in jsonList(d['items']))
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: DmCard(
                    child: Row(children: [
                      Expanded(
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text('${it['item_id']}', style: DmText.cardTitle),
                          Text('worn ${it['wear_count'] ?? 0}× · last ${it['last_worn'] ?? 'never'}', style: DmText.body),
                        ]),
                      ),
                      DmPill('${it['status'] ?? ''}', dark: it['status'] != 'available'),
                    ]),
                  ),
                ),
            ]);
          },
        ),
        const SizedBox(height: 16),
        const DmSectionHeader(eyebrow: 'Give them a second life', title: 'Forgotten pieces'),
        const SizedBox(height: 8),
        DmLoad(
          key: ValueKey('forgotten-$_run'),
          load: () => _api.call('/m03/forgotten', userId: DemoUsers.outfits),
          builder: (d, _) {
            final items = jsonList(d['items']);
            if (items.isEmpty) return const DmCard(child: Text('Nothing forgotten. Nice!', style: DmText.body));
            return Column(children: [
              for (final it in items)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: DmCard(
                    child: Row(children: [
                      const Icon(Icons.history_rounded, color: DmColors.warning),
                      const SizedBox(width: 10),
                      Expanded(child: Text('${it['item_id']} · not worn for ${it['days_since_worn']} days', style: DmText.body)),
                    ]),
                  ),
                ),
            ]);
          },
        ),
        const SizedBox(height: 16),
        const DmSectionHeader(eyebrow: 'Before you buy again', title: 'Duplicates in your wardrobe'),
        const SizedBox(height: 8),
        DmLoad(
          key: ValueKey('dups-$_run'),
          load: () => _api.post('/m01/duplicates', {'user_id': DemoUsers.wardrobe}),
          builder: (d, _) {
            final groups = (d['groups'] as List? ?? const []);
            if (groups.isEmpty) return const DmCard(child: Text('No duplicates found (M1).', style: DmText.body));
            return Column(children: [
              for (final g in groups)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: DmCard(child: Text(g is List ? 'Look alike: ${g.join('  ≈  ')}' : '$g', style: DmText.body)),
                ),
            ]);
          },
        ),
      ],
    );
  }
}

class _Stat extends StatelessWidget {
  const _Stat({required this.value, required this.label});

  final String value;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(value, style: DmText.display.copyWith(fontSize: 26)),
        Text(label, style: DmText.caption),
      ]),
    );
  }
}
