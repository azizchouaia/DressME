// Owner: BO7 · M10 — "Share studio": try every card type and see the BO7 acquisition KPIs.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../logic/challenges_providers.dart' show currentUserIdProvider;
import '../data/share_models.dart';
import '../logic/share_provider.dart';
import 'share_card_sheet.dart';

const _sampleItems = [
  CardItem(itemId: 'itm_t3', category: 'top', label: 'Linen shirt', colorHex: '#E3CFAE', brand: 'Sidi Linen Co.'),
  CardItem(itemId: 'itm_b3', category: 'bottom', label: 'Beige chinos', colorHex: '#D9C3A0'),
  CardItem(itemId: 'itm_s3', category: 'shoes', label: 'Brown loafers', colorHex: '#8A6446'),
  CardItem(itemId: 'itm_a1', category: 'accessory', label: 'Sage tote', colorHex: '#A8C3A0'),
];

class _Sample {
  const _Sample(this.label, this.icon, this.build);
  final String label;
  final IconData icon;
  final ShareCardRequest Function(String userId) build;
}

final _samples = <_Sample>[
  _Sample('Outfit of the day', Icons.wb_sunny_outlined, (u) => ShareCardRequest(
        userId: u, kind: CardKind.outfit, items: _sampleItems,
        title: 'Linen day at work', subtitle: 'Tuesday · 24°C · work')),
  _Sample('Builder board', Icons.dashboard_customize_outlined, (u) => ShareCardRequest(
        userId: u, kind: CardKind.board, items: _sampleItems, title: 'My look', format: CardFormat.square)),
  _Sample('Monthly recap', Icons.insights_outlined, (u) => ShareCardRequest(
        userId: u, kind: CardKind.recap, title: 'My month in outfits', subtitle: 'September 2026',
        stats: const [
          CardStat('outfits worn', '23'), CardStat('top colour', 'Beige'),
          CardStat('favourite (9 wears)', 'Jeans'), CardStat('cost per wear', '4.2 TND'),
        ])),
  _Sample('Give-away', Icons.volunteer_activism_outlined, (u) => ShareCardRequest(
        userId: u, kind: CardKind.giveaway, format: CardFormat.post,
        title: "I'm giving away this sweater", subtitle: 'Size M · good condition · Tunis',
        items: const [CardItem(itemId: 'itm_t6', category: 'top', label: 'Sage sweater', colorHex: '#A8C3A0')])),
  _Sample('Trip lookbook', Icons.luggage_outlined, (u) => ShareCardRequest(
        userId: u, kind: CardKind.trip, title: 'Djerba · 4 days', subtitle: '7 pieces, 4 outfits',
        items: _sampleItems.take(3).toList())),
];

class ShareScreen extends ConsumerWidget {
  const ShareScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final userId = ref.watch(currentUserIdProvider);
    final metrics = ref.watch(shareMetricsProvider(userId));
    return Scaffold(
      appBar: AppBar(title: const Text('Share studio')),
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(shareMetricsProvider(userId)),
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text('Your sharing impact', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            metrics.when(
              loading: () => const LinearProgressIndicator(),
              error: (_, __) => const Text('Metrics unavailable: is the server running?'),
              data: (m) => Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  _Kpi('Cards shared', '${m.cards}'),
                  _Kpi('Link opens', '${m.opens}'),
                  _Kpi('Friends who joined', '${m.signups}'),
                  _Kpi('K-factor', m.kFactor.toStringAsFixed(2)),
                ],
              ),
            ),
            const SizedBox(height: 24),
            Text('Create a card', style: Theme.of(context).textTheme.titleMedium),
            for (final s in _samples)
              ListTile(
                leading: Icon(s.icon),
                title: Text(s.label),
                trailing: const Icon(Icons.chevron_right),
                onTap: () async {
                  await showShareCardSheet(context, s.build(userId));
                  ref.invalidate(shareMetricsProvider(userId));
                },
              ),
          ],
        ),
      ),
    );
  }
}

class _Kpi extends StatelessWidget {
  const _Kpi(this.label, this.value);
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Container(
      width: 160,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: t.colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(value, style: t.textTheme.headlineSmall),
          Text(label, style: t.textTheme.bodySmall),
        ],
      ),
    );
  }
}
