// Owner: BO7 · M15 — "Défis": challenges sorted by the ML recommender, with how well my wardrobe fits each one.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/design/dressme_design.dart';
import '../data/bo7_models.dart';
import '../data/bo7_repository.dart';
import '../logic/bo7_providers.dart';
import 'challenge_detail_screen.dart';
import 'widgets.dart';

/// Pieces of my wardrobe that fit a challenge, to show on its card.
List<Garment> piecesFor(Challenge c, List<Garment> wardrobe) {
  Iterable<Garment> pool = wardrobe.where((g) => g.photoUrl != null);
  for (final r in c.rules) {
    if (r.type == 'color_theme') {
      final colors = (r.params['colors'] as List? ?? const []).map((e) => e.toString()).toSet();
      final keep = pool.where((g) => colors.contains(g.color));
      if (keep.isNotEmpty) pool = keep;
    } else if (r.type == 'category_required') {
      final cats = (r.params['categories'] as List? ?? const []).map((e) => e.toString()).toSet();
      final keep = pool.where((g) => cats.contains(g.category));
      if (keep.isNotEmpty) pool = keep.followedBy(pool.where((g) => !cats.contains(g.category)));
    } else if (r.type == 'local_brand') {
      final keep = pool.where((g) => g.isTunisian);
      if (keep.isNotEmpty) pool = keep;
    }
  }
  final out = <Garment>[];
  final cats = <String>{};
  for (final g in pool) {
    if (cats.add(g.category)) out.add(g);
    if (out.length == 3) break;
  }
  return out;
}

class ChallengesTab extends ConsumerWidget {
  const ChallengesTab({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider);
    final list = ref.watch(challengesProvider);
    final wardrobe = ref.watch(wardrobeProvider).valueOrNull ?? const <Garment>[];
    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(challengesProvider);
        ref.invalidate(wardrobeProvider);
      },
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
        children: [
          Bo7Hero(
            eyebrow: 'Défis de style · M15',
            title: 'Tes défis',
            subtitle: 'Rejoins un défi, note ce que tu portes chaque jour et partage la carte. '
                'Classés pour $user par le modèle de recommandation : garde-robe, popularité et style.',
          ),
          const SizedBox(height: 16),
          AsyncBody<List<Challenge>>(
            value: list,
            onRetry: () => ref.invalidate(challengesProvider),
            builder: (items) => LayoutBuilder(
              builder: (context, box) {
                final cols = box.maxWidth > 900 ? 3 : (box.maxWidth > 560 ? 2 : 1);
                final cards = [
                  for (final c in items) _ChallengeCard(challenge: c, pieces: piecesFor(c, wardrobe)),
                  const _CreateCard(),
                ];
                return Wrap(
                  spacing: 14,
                  runSpacing: 14,
                  children: [
                    for (final card in cards) SizedBox(width: (box.maxWidth - 14 * (cols - 1)) / cols, child: card),
                  ],
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _ChallengeCard extends StatelessWidget {
  const _ChallengeCard({required this.challenge, required this.pieces});

  final Challenge challenge;
  final List<Garment> pieces;

  @override
  Widget build(BuildContext context) {
    final c = challenge;
    final fit = c.feasibility ?? 0;
    final fitColor = fit >= 1 ? DmColors.success : (fit >= 0.6 ? DmColors.bronze : const Color(0xFFB0573E));
    return InkWell(
      borderRadius: BorderRadius.circular(DmRadius.panel),
      onTap: () => Navigator.of(context).push(
        MaterialPageRoute<void>(
            builder: (_) => Theme(data: dressMeTheme(), child: ChallengeDetailScreen(challengeId: c.id))),
      ),
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: DmColors.surface,
          borderRadius: BorderRadius.circular(DmRadius.panel),
          border: Border.all(color: DmColors.border),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // the "door": dark arch with the pieces inside (Figma walnut + gold)
            Container(
              height: 170,
              padding: const EdgeInsets.all(7),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [Color(0xFF2B241E), DmColors.inkDeep],
                ),
                borderRadius: const BorderRadius.vertical(top: Radius.circular(90), bottom: Radius.circular(14)),
                border: Border.all(color: DmColors.gold.withValues(alpha: 0.4)),
              ),
              child: Container(
                decoration: const BoxDecoration(
                  color: DmColors.canvas,
                  borderRadius: BorderRadius.vertical(top: Radius.circular(84), bottom: Radius.circular(8)),
                ),
                padding: const EdgeInsets.fromLTRB(12, 30, 12, 8),
                child: Stack(
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: pieces.isEmpty
                          ? [
                              const Expanded(
                                  child:
                                      Center(child: Text('Ajoute des photos dans Garde-robe', style: DmText.caption)))
                            ]
                          : [for (final g in pieces) Expanded(child: GarmentImage(g))],
                    ),
                    if (c.joined) const Positioned(top: 0, right: 0, child: DmPill('Inscrit·e', dark: true)),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(child: Text(c.title, style: DmText.cardTitle)),
                DmPill('${c.durationDays} jours'),
              ],
            ),
            const SizedBox(height: 4),
            Text(c.description, maxLines: 2, overflow: TextOverflow.ellipsis, style: DmText.body),
            const SizedBox(height: 8),
            Wrap(
              spacing: 6,
              runSpacing: 4,
              children: [
                DmPill('${c.participants} inscrits'),
                if (c.sponsor != null) DmPill('Sponsorisé par ${c.sponsor}'),
                if (c.createdBy != 'dressme') DmPill('par ${c.createdBy}'),
                if (c.tags.contains('local') || c.rules.any((r) => r.type == 'local_brand'))
                  const DmPill('Créateurs tunisiens'),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                const Expanded(child: Text('Adapté à ta garde-robe', style: DmText.caption)),
                Text('${(fit * 100).round()} %', style: DmText.price.copyWith(color: fitColor)),
              ],
            ),
            const SizedBox(height: 4),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(value: fit.clamp(0, 1).toDouble(), minHeight: 5, color: fitColor),
            ),
          ],
        ),
      ),
    );
  }
}

class _CreateCard extends ConsumerWidget {
  const _CreateCard();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return InkWell(
      borderRadius: BorderRadius.circular(DmRadius.panel),
      onTap: () => showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        builder: (_) => Theme(data: dressMeTheme(), child: const _CreateChallengeSheet()),
      ),
      child: Container(
        height: 180,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(DmRadius.panel),
          border: Border.all(color: DmColors.borderStrong, width: 1.5),
          color: DmColors.surface.withValues(alpha: 0.6),
        ),
        child: const Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.add_circle_outline, size: 36, color: DmColors.bronze),
              SizedBox(height: 6),
              Text('Créer un défi', style: DmText.cardTitle),
              Text('Pour tes amies, ou pour une marque tunisienne', style: DmText.caption),
            ],
          ),
        ),
      ),
    );
  }
}

class _CreateChallengeSheet extends ConsumerStatefulWidget {
  const _CreateChallengeSheet();

  @override
  ConsumerState<_CreateChallengeSheet> createState() => _CreateChallengeSheetState();
}

class _CreateChallengeSheetState extends ConsumerState<_CreateChallengeSheet> {
  final _title = TextEditingController();
  final _desc = TextEditingController();
  int _days = 7;
  bool _noRepeat = true;
  bool _local = false;
  String? _color;
  bool _busy = false;

  static const _colors = {'black': 'Noir', 'white': 'Blanc', 'red': 'Rouge', 'blue': 'Bleu', 'beige': 'Beige'};

  Future<void> _publish() async {
    final rules = <Map<String, dynamic>>[
      if (_noRepeat) {'type': 'no_repeat', 'params': <String, dynamic>{}},
      if (_local)
        {
          'type': 'local_brand',
          'params': {'min': 1}
        },
      if (_color != null)
        {
          'type': 'color_theme',
          'params': {
            'colors': [_color],
            'mode': 'any'
          },
        },
    ];
    if (_title.text.trim().isEmpty || rules.isEmpty) {
      showSnack(context, 'Donne un titre et au moins une règle.');
      return;
    }
    setState(() => _busy = true);
    try {
      await ref.read(bo7RepositoryProvider).createChallenge(
            userId: ref.read(currentUserProvider),
            title: _title.text.trim(),
            description: _desc.text.trim().isEmpty ? _title.text.trim() : _desc.text.trim(),
            durationDays: _days,
            rules: rules,
          );
      ref.invalidate(challengesProvider);
      if (mounted) {
        Navigator.pop(context);
        showSnack(context, 'Défi publié');
      }
    } on Bo7Exception catch (e) {
      if (mounted) showSnack(context, e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.fromLTRB(20, 20, 20, 20 + MediaQuery.of(context).viewInsets.bottom),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const DmSectionHeader(eyebrow: 'Nouveau défi', title: 'Créer un défi'),
            const SizedBox(height: 14),
            TextField(controller: _title, decoration: const InputDecoration(hintText: 'Titre (ex. Vendredi tunisien)')),
            const SizedBox(height: 8),
            TextField(controller: _desc, maxLines: 2, decoration: const InputDecoration(hintText: 'Description')),
            const SizedBox(height: 12),
            Text('Durée : $_days jours', style: DmText.itemName),
            Slider(
                value: _days.toDouble(),
                min: 3,
                max: 14,
                divisions: 11,
                onChanged: (v) => setState(() => _days = v.round())),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              value: _noRepeat,
              onChanged: (v) => setState(() => _noRepeat = v),
              title: const Text('Aucune pièce portée deux fois', style: DmText.itemName),
            ),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              value: _local,
              onChanged: (v) => setState(() => _local = v),
              title: const Text('Une pièce d\'un créateur tunisien chaque jour', style: DmText.itemName),
            ),
            const SizedBox(height: 6),
            const Text('Couleur du défi (facultatif)', style: DmText.itemName),
            const SizedBox(height: 6),
            Wrap(
              spacing: 6,
              children: [
                for (final e in _colors.entries)
                  ChoiceChip(
                    label: Text(e.value),
                    selected: _color == e.key,
                    onSelected: (s) => setState(() => _color = s ? e.key : null),
                  ),
              ],
            ),
            const SizedBox(height: 18),
            FilledButton(onPressed: _busy ? null : _publish, child: Text(_busy ? 'Publication…' : 'Publier le défi')),
          ],
        ),
      ),
    );
  }
}
