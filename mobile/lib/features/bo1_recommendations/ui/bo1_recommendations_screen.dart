// Owner: BO1 (Racem) — personalised outfit recommendations (M2), "I wore it" (M3). Integration screen.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/dm_api.dart';
import '../../../core/design/dressme_design.dart';
import '../../../core/widgets/dm_async.dart';
import '../../../core/widgets/dm_widgets.dart';

const _occasions = ['casual', 'work', 'evening', 'wedding', 'sport'];
const _moods = ['confident', 'relaxed', 'bold', 'calm'];

class RecommendationsScreen extends ConsumerStatefulWidget {
  const RecommendationsScreen({super.key});

  @override
  ConsumerState<RecommendationsScreen> createState() => _RecommendationsScreenState();
}

class _RecommendationsScreenState extends ConsumerState<RecommendationsScreen> {
  String _occasion = 'work';
  String? _mood;
  final _city = TextEditingController(text: 'Tunis');
  int _run = 0; // bump to re-ask M2

  @override
  void dispose() {
    _city.dispose();
    super.dispose();
  }

  Future<Json> _load() => ref.read(dmApiProvider).call('/m02/recommend', userId: DemoUsers.outfits, payload: {
        'context': {'occasion': _occasion, 'mood': _mood, 'city': _city.text.trim().isEmpty ? 'Tunis' : _city.text.trim()},
      });

  @override
  Widget build(BuildContext context) {
    return DmPage(
      eyebrow: 'BO1 · Outfits for you',
      title: 'What should I wear?',
      children: [
        DmCard(
          big: true,
          padding: const EdgeInsets.all(18),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('Occasion'.toUpperCase(), style: DmText.eyebrow),
            const SizedBox(height: 8),
            Wrap(spacing: 6, runSpacing: 6, children: [
              for (final o in _occasions)
                DmChoiceChip(label: cap(o), selected: _occasion == o, onTap: () => setState(() => _occasion = o)),
            ]),
            const SizedBox(height: 14),
            Text('Mood (optional)'.toUpperCase(), style: DmText.eyebrow),
            const SizedBox(height: 8),
            Wrap(spacing: 6, runSpacing: 6, children: [
              for (final m in _moods)
                DmChoiceChip(label: cap(m), selected: _mood == m, onTap: () => setState(() => _mood = _mood == m ? null : m)),
            ]),
            const SizedBox(height: 12),
            TextField(controller: _city, decoration: const InputDecoration(labelText: 'City (for the weather)')),
            const SizedBox(height: 14),
            DmButton('Suggest outfits', kind: DmButtonKind.gold, icon: Icons.auto_awesome, onPressed: () => setState(() => _run++)),
          ]),
        ),
        const SizedBox(height: 18),
        DmLoad(
          key: ValueKey('rec-$_run'),
          load: _load,
          builder: (data, _) => _Outfits(data: data),
        ),
      ],
    );
  }
}

class _Outfits extends ConsumerWidget {
  const _Outfits({required this.data});

  final Json data;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final outfits = jsonList(data['outfits']);
    final items = (data['items'] as Map? ?? const {}).cast<String, dynamic>();
    final weather = (data['context'] as Map?)?['weather'] as Map?;
    if (outfits.isEmpty) {
      return const DmCard(child: DmEmptyState(title: 'No outfit', message: 'M2 found nothing for this context.'));
    }
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Row(children: [
        Expanded(
          child: Text(
            weather == null ? 'Your outfits' : 'Your outfits · ${weather['temp_c']}°C, ${weather['condition']}',
            style: DmText.cardTitle,
          ),
        ),
        DmSource(mocked: data['_mocked'] == true, label: 'M2'),
      ]),
      const SizedBox(height: 10),
      for (final (i, o) in outfits.take(3).indexed)
        Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: DmCard(
            padding: const EdgeInsets.all(16),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Text('Outfit ${i + 1}', style: DmText.title.copyWith(fontSize: 20)),
                const Spacer(),
                DmPill('Score ${pct(o['score'])}'),
              ]),
              const SizedBox(height: 10),
              SizedBox(
                height: 150,
                child: ListView(scrollDirection: Axis.horizontal, children: [
                  for (final id in (o['items'] as List? ?? const []))
                    Padding(
                      padding: const EdgeInsets.only(right: 10),
                      child: DmPieceTile(
                        name: '${(items['$id'] as Map?)?['name'] ?? id}',
                        imageUrl: ref.read(dmApiProvider).media((items['$id'] as Map?)?['image'] as String?),
                        caption: '${(items['$id'] as Map?)?['category'] ?? ''}',
                        width: 100,
                      ),
                    ),
                ]),
              ),
              const SizedBox(height: 8),
              Text('${o['explanation'] ?? ''}', style: DmText.body),
              const SizedBox(height: 8),
              Wrap(spacing: 6, runSpacing: 6, children: [
                for (final e in ((o['score_breakdown'] as Map?) ?? const {}).entries.where((e) => e.value is num && e.value > 0).take(4))
                  DmPill('${e.key.toString().replaceAll('_', ' ')} ${pct(e.value)}'),
              ]),
              const SizedBox(height: 12),
              DmButton('I wear this today', kind: DmButtonKind.dark, icon: Icons.check_rounded, onPressed: () async {
                try {
                  await ref.read(dmApiProvider).call('/m03/worn', userId: DemoUsers.outfits, payload: {
                    'item_ids': o['items'],
                    'outfit_id': o['outfit_id'],
                  });
                  if (context.mounted) dmToast(context, 'Logged in your wear log (M3)');
                } catch (e) {
                  if (context.mounted) dmToast(context, apiError(e));
                }
              }),
            ]),
          ),
        ),
    ]);
  }
}
