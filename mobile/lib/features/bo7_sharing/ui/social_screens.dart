// Owner: BO7 — the other BO7 ideas, opened from the Studio: "Should I buy this?" poll (M6), monthly recap (M3),
// give-away (M1 duplicates + M3), trip lookbook (M11), style timeline (M12), recreate a look from a photo (M1, M2),
// stylist mode (M14) and the looks a stylist sent me. Every card is drawn by M10 and can be posted in the feed.
// The other teams' modules are mocked server-side until they are built ("simulé" next to the module).
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../../core/design/dressme_design.dart';
import '../data/bo7_models.dart';
import '../data/bo7_repository.dart';
import '../data/bo7_social_models.dart';
import '../logic/bo7_providers.dart';
import 'feed_widgets.dart';
import 'share_result.dart';
import 'widgets.dart';

/// Entry of the Studio "more ideas" panel.
class SocialIdea {
  const SocialIdea(this.label, this.hint, this.icon, this.modules, this.builder);
  final String label;
  final String hint;
  final IconData icon;
  final String modules;
  final Widget Function() builder;
}

final socialIdeas = [
  SocialIdea(
      'Je l\'achète ?', 'sondage pour tes amis', Icons.how_to_vote_outlined, 'M6 + M10', () => const PollScreen()),
  SocialIdea(
      'Bilan du mois', 'tes chiffres, façon Wrapped', Icons.insights_outlined, 'M3 + M10', () => const RecapScreen()),
  SocialIdea('Je donne', 'pièces en double ou jamais portées', Icons.volunteer_activism_outlined, 'M1 + M3',
      () => const GiveawayScreen()),
  SocialIdea('Voyage', 'lookbook et valise', Icons.luggage_outlined, 'M11 + M10', () => const TripScreen()),
  SocialIdea('Mon style', 'son évolution mois par mois', Icons.timeline, 'M12 + M10', () => const TimelineScreen()),
  SocialIdea('Recréer une photo', 'un look vu ailleurs, avec tes pièces', Icons.autorenew_rounded, 'M1 + M2',
      () => const RecreatePhotoScreen()),
  SocialIdea('Mode styliste', 'envoyer un look à une cliente', Icons.design_services_outlined, 'M14',
      () => const StylistScreen()),
  SocialIdea('Looks de ma styliste', 'ce qu\'on m\'a envoyé', Icons.inbox_outlined, 'M14', () => const InboxScreen()),
];

Future<void> openIdea(BuildContext context, SocialIdea idea) => Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => Theme(data: dressMeTheme(), child: idea.builder())),
    );

/// Who answered: the owner's module, or the BO7 mock ("simulé") until the team ships it.
class SourcesLine extends StatelessWidget {
  const SourcesLine(this.sources, {super.key});

  final Map<String, String> sources;

  @override
  Widget build(BuildContext context) {
    final parts = [
      for (final e in sources.entries)
        if (e.value != 'n/a') '${e.key} : ${e.value == 'mock' ? 'simulé (mock)' : e.value}'
    ];
    return Text(parts.join(' · '), style: DmText.caption);
  }
}

/// The card of a feature + "post in the feed".
class SocialResult extends ConsumerStatefulWidget {
  const SocialResult({super.key, required this.result, this.title});

  final SocialCard result;
  final String? title;

  @override
  ConsumerState<SocialResult> createState() => _SocialResultState();
}

class _SocialResultState extends ConsumerState<SocialResult> {
  bool _posted = false;

  Future<void> _publish() async {
    try {
      await ref
          .read(bo7RepositoryProvider)
          .publish(ref.read(currentUserProvider), widget.result.card.cardId, title: widget.title);
      refreshFeed(ref);
      setState(() => _posted = true);
      if (mounted) showSnack(context, 'Publié dans le fil');
    } on Bo7Exception catch (e) {
      if (mounted) showSnack(context, e.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    final inFeed = _posted || widget.result.post != null;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SourcesLine(widget.result.sources),
        const SizedBox(height: 8),
        ShareResult(key: ValueKey(widget.result.card.cardId), card: widget.result.card),
        const SizedBox(height: 10),
        inFeed
            ? const Text('Dans le fil de la communauté.', style: DmText.itemName)
            : FilledButton.icon(
                onPressed: _publish,
                icon: const Icon(Icons.send_rounded, size: 18),
                label: const Text('Publier dans le fil'),
              ),
      ],
    );
  }
}

class _Page extends StatelessWidget {
  const _Page({required this.title, required this.eyebrow, required this.subtitle, required this.children});

  final String title;
  final String eyebrow;
  final String subtitle;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 4, 16, 32),
        children: [
          Bo7Hero(eyebrow: eyebrow, title: title, subtitle: subtitle),
          const SizedBox(height: 14),
          ...children
        ],
      ),
    );
  }
}

mixin _Busy<T extends ConsumerStatefulWidget> on ConsumerState<T> {
  bool busy = false;

  Future<R?> run<R>(Future<R> Function() f) async {
    setState(() => busy = true);
    try {
      return await f();
    } on Bo7Exception catch (e) {
      if (mounted) showSnack(context, e.message);
      return null;
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }
}

// ------------------------------------------------------------------------ "Should I buy this?" poll
const _pollColours = {
  'noir': '#1E1E1E',
  'blanc': '#F2F0EA',
  'beige': '#D9C7A8',
  'rouge': '#A8312C',
  'bleu': '#2F4F8F',
  'vert': '#4E7B55',
  'rose': '#E3A2B4',
  'jaune': '#E2B93B',
};

class PollScreen extends ConsumerStatefulWidget {
  const PollScreen({super.key});

  @override
  ConsumerState<PollScreen> createState() => _PollScreenState();
}

class _PollScreenState extends ConsumerState<PollScreen> with _Busy {
  final _label = TextEditingController(text: 'veste en cuir');
  final _price = TextEditingController();
  final _shop = TextEditingController();
  String _category = 'outerwear';
  String _colour = 'rouge';
  String? _photo;
  SocialCard? _result;

  Future<void> _pick() async {
    final f = await ImagePicker().pickImage(source: ImageSource.gallery, maxWidth: 1000);
    if (f == null) return;
    final bytes = await f.readAsBytes();
    setState(() => _photo = 'data:${f.mimeType ?? 'image/jpeg'};base64,${base64Encode(bytes)}');
  }

  Future<void> _create() async {
    final r = await run(() => ref.read(bo7RepositoryProvider).createPoll(ref.read(currentUserProvider), {
          'label': _label.text.trim().isEmpty ? 'pièce' : _label.text.trim(),
          'category': _category,
          'color_hex': _pollColours[_colour],
          if (_photo != null) 'image': _photo,
          if (double.tryParse(_price.text) != null) 'price_tnd': double.parse(_price.text),
          if (_shop.text.trim().isNotEmpty) 'shop': _shop.text.trim(),
        }));
    if (r != null) {
      setState(() => _result = r);
      refreshFeed(ref);
    }
  }

  @override
  Widget build(BuildContext context) {
    return _Page(
      title: 'Je l\'achète ?',
      eyebrow: 'Sondage · M6 Smart Buy + M10',
      subtitle: 'Tu hésites devant une pièce en boutique ? L\'IA compare avec ta garde-robe, puis tes amis votent.',
      children: [
        Bo7Panel(
          title: 'La pièce',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              TextField(controller: _label, decoration: const InputDecoration(labelText: 'Nom de la pièce')),
              const SizedBox(height: 10),
              PillChoice<String>(
                options: const ['top', 'bottom', 'dress', 'outerwear', 'shoes', 'accessory'],
                selected: _category,
                label: (c) => categoryLabels[c] ?? c,
                onSelected: (c) => setState(() => _category = c),
              ),
              const SizedBox(height: 10),
              Wrap(
                spacing: 8,
                children: [
                  for (final e in _pollColours.entries)
                    ChoiceChip(
                      avatar: CircleAvatar(backgroundColor: hexColor(e.value), radius: 8),
                      label: Text(e.key),
                      selected: _colour == e.key,
                      onSelected: (_) => setState(() => _colour = e.key),
                    ),
                ],
              ),
              const SizedBox(height: 10),
              Row(children: [
                Expanded(
                    child: TextField(
                        controller: _price,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(labelText: 'Prix (DT)'))),
                const SizedBox(width: 10),
                Expanded(child: TextField(controller: _shop, decoration: const InputDecoration(labelText: 'Boutique'))),
              ]),
              const SizedBox(height: 10),
              OutlinedButton.icon(
                onPressed: _pick,
                icon: const Icon(Icons.photo_camera_outlined, size: 18),
                label: Text(_photo == null ? 'Ajouter la photo de la pièce' : 'Photo ajoutée ✓'),
              ),
              const SizedBox(height: 12),
              FilledButton.icon(
                onPressed: busy ? null : _create,
                icon: const Icon(Icons.how_to_vote_outlined, size: 18),
                label: Text(busy ? 'Avis de l\'IA…' : 'Demander l\'avis de l\'IA et de mes amis'),
              ),
            ],
          ),
        ),
        if (_result != null) ...[
          const SizedBox(height: 14),
          if (_result!.post?.poll != null) PollBox(poll: _result!.post!.poll!),
          const SizedBox(height: 10),
          SocialResult(result: _result!),
        ],
      ],
    );
  }
}

// ------------------------------------------------------------------------ monthly recap
class RecapScreen extends ConsumerStatefulWidget {
  const RecapScreen({super.key});

  @override
  ConsumerState<RecapScreen> createState() => _RecapScreenState();
}

class _RecapScreenState extends ConsumerState<RecapScreen> with _Busy {
  int _back = 0; // 0 = this month
  SocialCard? _result;

  String get _month {
    final now = DateTime.now();
    final d = DateTime(now.year, now.month - _back);
    return '${d.year}-${d.month.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    final stats = (_result?.extra['stats'] as List?)?.whereType<Map>().toList() ?? const [];
    return _Page(
      title: 'Bilan du mois',
      eyebrow: 'Wrapped · M3 wear log + M10',
      subtitle: 'Combien de tenues, quelles pièces tu portes le plus, et ce qui dort dans ton placard.',
      children: [
        Bo7Panel(
          title: 'Quel mois ?',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              PillChoice<int>(
                options: const [0, 1, 2],
                selected: _back,
                label: (b) => ['Ce mois-ci', 'Le mois dernier', 'Il y a 2 mois'][b],
                onSelected: (b) => setState(() => _back = b),
              ),
              const SizedBox(height: 12),
              FilledButton.icon(
                onPressed: busy
                    ? null
                    : () async {
                        final r = await run(
                            () => ref.read(bo7RepositoryProvider).recap(ref.read(currentUserProvider), month: _month));
                        if (r != null) setState(() => _result = r);
                      },
                icon: const Icon(Icons.insights_outlined, size: 18),
                label: Text(busy ? 'Calcul…' : 'Faire mon bilan de $_month'),
              ),
            ],
          ),
        ),
        if (_result != null) ...[
          const SizedBox(height: 14),
          Wrap(spacing: 8, runSpacing: 8, children: [
            for (final s in stats) StatTile('${s['value']}', '${s['label']}'),
          ]),
          const SizedBox(height: 12),
          SocialResult(result: _result!, title: 'Mon $_month'),
        ],
      ],
    );
  }
}

// ------------------------------------------------------------------------ give-away
class GiveawayScreen extends ConsumerStatefulWidget {
  const GiveawayScreen({super.key, this.itemId});

  final String? itemId;

  @override
  ConsumerState<GiveawayScreen> createState() => _GiveawayScreenState();
}

class _GiveawayScreenState extends ConsumerState<GiveawayScreen> with _Busy {
  String? _item;
  String _condition = 'bon état';
  final _size = TextEditingController();
  final _city = TextEditingController(text: 'Tunis');
  SocialCard? _result;

  @override
  void initState() {
    super.initState();
    _item = widget.itemId;
  }

  @override
  Widget build(BuildContext context) {
    return _Page(
      title: 'Je donne',
      eyebrow: 'Don · M1 doublons + M3 jamais portées',
      subtitle: 'Offre à tes amis ce que tu ne portes plus. Ils la demandent dans le fil, tu choisis qui la reçoit.',
      children: [
        Bo7Panel(
          title: '1. La pièce à donner',
          subtitle: 'Suggestions : pièces en double, ou pas portées ce mois-ci.',
          child: AsyncBody<List<TaggedPiece>>(
            value: ref.watch(giveawaySuggestionsProvider),
            onRetry: () => ref.invalidate(giveawaySuggestionsProvider),
            builder: (items) => items.isEmpty && _item == null
                ? const Text('Rien à donner : ta garde-robe tourne bien !', style: DmText.body)
                : SizedBox(
                    height: 170,
                    child: ListView(
                      scrollDirection: Axis.horizontal,
                      children: [
                        for (final p in items)
                          SizedBox(
                            width: 120,
                            child: Padding(
                              padding: const EdgeInsets.only(right: 8),
                              child: Column(
                                children: [
                                  Expanded(
                                    child: GarmentTile(
                                      garment: p.toGarment(),
                                      selected: _item == p.itemId,
                                      onTap: () => setState(() => _item = p.itemId),
                                    ),
                                  ),
                                  Text(p.reason ?? '', maxLines: 2, textAlign: TextAlign.center, style: DmText.caption),
                                ],
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
          ),
        ),
        const SizedBox(height: 12),
        Bo7Panel(
          title: '2. Les détails',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              PillChoice<String>(
                options: const ['comme neuf', 'bon état', 'usé'],
                selected: _condition,
                label: (c) => c,
                onSelected: (c) => setState(() => _condition = c),
              ),
              const SizedBox(height: 8),
              Row(children: [
                Expanded(child: TextField(controller: _size, decoration: const InputDecoration(labelText: 'Taille'))),
                const SizedBox(width: 10),
                Expanded(child: TextField(controller: _city, decoration: const InputDecoration(labelText: 'Ville'))),
              ]),
              const SizedBox(height: 12),
              FilledButton.icon(
                onPressed: busy || _item == null
                    ? null
                    : () async {
                        final r = await run(() => ref.read(bo7RepositoryProvider).createGiveaway(
                            ref.read(currentUserProvider), _item!,
                            size: _size.text.trim(), condition: _condition, city: _city.text.trim()));
                        if (r != null) {
                          setState(() => _result = r);
                          ref.invalidate(giveawaySuggestionsProvider);
                          refreshFeed(ref);
                        }
                      },
                icon: const Icon(Icons.volunteer_activism_outlined, size: 18),
                label: Text(busy ? 'Publication…' : 'Publier le don dans le fil'),
              ),
            ],
          ),
        ),
        if (_result != null) ...[const SizedBox(height: 14), SocialResult(result: _result!)],
      ],
    );
  }
}

// ------------------------------------------------------------------------ trip lookbook
class TripScreen extends ConsumerStatefulWidget {
  const TripScreen({super.key});

  @override
  ConsumerState<TripScreen> createState() => _TripScreenState();
}

class _TripScreenState extends ConsumerState<TripScreen> with _Busy {
  final _dest = TextEditingController(text: 'Djerba');
  double _days = 4;
  SocialCard? _result;

  @override
  Widget build(BuildContext context) {
    final plan = (_result?.extra['plan'] as List?)?.whereType<Map>().toList() ?? const [];
    final packing = (_result?.extra['packing'] as List?)?.length ?? 0;
    return _Page(
      title: 'Voyage',
      eyebrow: 'Lookbook · M11 trip planner + M10',
      subtitle: 'Une tenue par jour avec le moins de pièces possible, et la carte à partager.',
      children: [
        Bo7Panel(
          title: 'Ton voyage',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              TextField(controller: _dest, decoration: const InputDecoration(labelText: 'Destination')),
              const SizedBox(height: 10),
              Text('${_days.round()} jours', style: DmText.itemName),
              Slider(value: _days, min: 1, max: 14, divisions: 13, onChanged: (v) => setState(() => _days = v)),
              FilledButton.icon(
                onPressed: busy
                    ? null
                    : () async {
                        final r = await run(() => ref
                            .read(bo7RepositoryProvider)
                            .trip(ref.read(currentUserProvider), _dest.text.trim(), _days.round()));
                        if (r != null) setState(() => _result = r);
                      },
                icon: const Icon(Icons.luggage_outlined, size: 18),
                label: Text(busy ? 'Préparation…' : 'Préparer ma valise'),
              ),
            ],
          ),
        ),
        if (_result != null) ...[
          const SizedBox(height: 14),
          Bo7Panel(
            title: '$packing pièces pour ${plan.length} jours',
            child: Column(children: [
              for (final d in plan)
                ListTile(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  leading: CircleAvatar(radius: 13, child: Text('${d['day']}')),
                  title: Text('${(d['item_ids'] as List?)?.length ?? 0} pièces', style: DmText.itemName),
                ),
            ]),
          ),
          const SizedBox(height: 12),
          SocialResult(result: _result!),
        ],
      ],
    );
  }
}

// ------------------------------------------------------------------------ style timeline
class TimelineScreen extends ConsumerStatefulWidget {
  const TimelineScreen({super.key});

  @override
  ConsumerState<TimelineScreen> createState() => _TimelineScreenState();
}

class _TimelineScreenState extends ConsumerState<TimelineScreen> with _Busy {
  double _months = 4;
  SocialCard? _result;

  @override
  Widget build(BuildContext context) {
    final months = (_result?.extra['months'] as List?)?.whereType<Map>().toList() ?? const [];
    return _Page(
      title: 'Mon style',
      eyebrow: 'Évolution · M12 style tracker + M10',
      subtitle: 'Comment ton style a changé mois après mois, en une carte.',
      children: [
        Bo7Panel(
          title: 'Sur combien de mois ?',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text('${_months.round()} mois', style: DmText.itemName),
              Slider(value: _months, min: 2, max: 12, divisions: 10, onChanged: (v) => setState(() => _months = v)),
              FilledButton.icon(
                onPressed: busy
                    ? null
                    : () async {
                        final r = await run(() => ref
                            .read(bo7RepositoryProvider)
                            .timeline(ref.read(currentUserProvider), months: _months.round()));
                        if (r != null) setState(() => _result = r);
                      },
                icon: const Icon(Icons.timeline, size: 18),
                label: Text(busy ? 'Analyse…' : 'Voir mon évolution'),
              ),
            ],
          ),
        ),
        if (_result != null) ...[
          const SizedBox(height: 14),
          Bo7Panel(
            title: '${_result!.extra['title'] ?? ''}',
            child: Column(children: [
              for (final m in months)
                ListTile(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  title: Text('${m['month']}', style: DmText.itemName),
                  trailing: DmPill('${m['style']}'),
                  subtitle: Text('couleur : ${m['main_colour']}', style: DmText.caption),
                ),
            ]),
          ),
          const SizedBox(height: 12),
          SocialResult(result: _result!),
        ],
      ],
    );
  }
}

// ------------------------------------------------------------------------ recreate from a photo
class RecreatePhotoScreen extends ConsumerStatefulWidget {
  const RecreatePhotoScreen({super.key});

  @override
  ConsumerState<RecreatePhotoScreen> createState() => _RecreatePhotoScreenState();
}

class _RecreatePhotoScreenState extends ConsumerState<RecreatePhotoScreen> with _Busy {
  String? _photo;
  RecreateResult? _result;

  Future<void> _pick() async {
    final f = await ImagePicker().pickImage(source: ImageSource.gallery, maxWidth: 900);
    if (f == null) return;
    final bytes = await f.readAsBytes();
    setState(() {
      _photo = 'data:${f.mimeType ?? 'image/jpeg'};base64,${base64Encode(bytes)}';
      _result = null;
    });
    final r = await run(() => ref.read(bo7RepositoryProvider).recreate(ref.read(currentUserProvider), photo: _photo));
    if (r != null) setState(() => _result = r);
  }

  @override
  Widget build(BuildContext context) {
    return _Page(
      title: 'Recréer une photo',
      eyebrow: 'Recréer · M1 analyse + M2 correspondance',
      subtitle: 'Un look vu sur Instagram ou chez une amie ? Envoie la photo : on le refait avec tes pièces.',
      children: [
        FilledButton.icon(
          onPressed: busy ? null : _pick,
          icon: const Icon(Icons.photo_library_outlined, size: 18),
          label: Text(busy ? 'Analyse de la photo…' : 'Choisir la photo du look'),
        ),
        const SizedBox(height: 6),
        const Text('Pour le recréer depuis le fil, appuie sur « Recréer » sous le look d\'une amie.',
            style: DmText.caption),
        if (_result != null) ...[
          const SizedBox(height: 14),
          SourcesLine(_result!.sources),
          const SizedBox(height: 8),
          RecreateView(result: _result!, ownerName: 'la photo'),
        ],
      ],
    );
  }
}

// ------------------------------------------------------------------------ stylist mode
class StylistScreen extends ConsumerStatefulWidget {
  const StylistScreen({super.key});

  @override
  ConsumerState<StylistScreen> createState() => _StylistScreenState();
}

class _StylistScreenState extends ConsumerState<StylistScreen> with _Busy {
  String? _stylist;
  String? _client;
  final Set<String> _picked = {};
  final _note = TextEditingController();

  @override
  Widget build(BuildContext context) {
    return _Page(
      title: 'Mode styliste',
      eyebrow: 'Styliste · M14 boutique mode',
      subtitle: 'Une styliste compose un look avec la garde-robe de sa cliente et le lui envoie.',
      children: [
        Bo7Panel(
          title: '1. La styliste',
          child: AsyncBody<List<Stylist>>(
            value: ref.watch(stylistsProvider),
            compact: true,
            builder: (rows) => Wrap(spacing: 8, children: [
              for (final s in rows)
                ChoiceChip(
                  label: Text(s.name),
                  selected: _stylist == s.id,
                  onSelected: (_) => setState(() {
                    _stylist = s.id;
                    _client = null;
                    _picked.clear();
                  }),
                ),
            ]),
          ),
        ),
        if (_stylist != null) ...[
          const SizedBox(height: 12),
          Bo7Panel(
            title: '2. La cliente',
            child: AsyncBody<List<StylistClient>>(
              value: ref.watch(stylistClientsProvider(_stylist!)),
              compact: true,
              builder: (rows) => Wrap(spacing: 8, children: [
                for (final c in rows)
                  ChoiceChip(
                    label: Text(c.name),
                    selected: _client == c.id,
                    onSelected: (_) => setState(() {
                      _client = c.id;
                      _picked.clear();
                    }),
                  ),
              ]),
            ),
          ),
        ],
        if (_client != null) ...[
          const SizedBox(height: 12),
          Bo7Panel(
            title: '3. Le look, avec ses pièces',
            child: AsyncBody<List<Garment>>(
              value: ref.watch(userWardrobeProvider(_client!)),
              compact: true,
              builder: (items) => Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  GarmentPicker(
                    garments: items,
                    selected: _picked,
                    onToggle: (g) => setState(() => _picked.contains(g.id) ? _picked.remove(g.id) : _picked.add(g.id)),
                  ),
                  TextField(controller: _note, decoration: const InputDecoration(labelText: 'Un mot pour la cliente')),
                  const SizedBox(height: 10),
                  FilledButton.icon(
                    onPressed: busy || _picked.isEmpty
                        ? null
                        : () async {
                            final ok = await run(() async {
                              await ref
                                  .read(bo7RepositoryProvider)
                                  .stylistShare(_stylist!, _client!, _picked.toList(), note: _note.text.trim());
                              return true;
                            });
                            if (ok == true && context.mounted) {
                              showSnack(context, 'Look envoyé : il est dans « Looks de ma styliste » de la cliente.');
                              setState(_picked.clear);
                            }
                          },
                    icon: const Icon(Icons.send_rounded, size: 18),
                    label: Text(busy ? 'Envoi…' : 'Envoyer le look'),
                  ),
                ],
              ),
            ),
          ),
        ],
      ],
    );
  }
}

class InboxScreen extends ConsumerWidget {
  const InboxScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final repo = ref.read(bo7RepositoryProvider);
    return _Page(
      title: 'Looks de ma styliste',
      eyebrow: 'Styliste · M14',
      subtitle: 'Les looks que ta styliste a composés avec tes propres pièces.',
      children: [
        AsyncBody<List<InboxLook>>(
          value: ref.watch(inboxProvider),
          onRetry: () => ref.invalidate(inboxProvider),
          builder: (rows) => rows.isEmpty
              ? const Bo7Panel(title: 'Rien pour l\'instant', child: Text('Aucun look reçu.', style: DmText.body))
              : Column(children: [
                  for (final l in rows)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: Bo7Panel(
                        title: l.stylistName,
                        subtitle: l.note,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            if (l.imageUrl != null)
                              Container(
                                color: DmColors.sand,
                                constraints: const BoxConstraints(maxHeight: 380),
                                child: Image.network(repo.url(l.imageUrl!), fit: BoxFit.contain),
                              ),
                            if (l.shareUrl != null)
                              TextButton.icon(
                                onPressed: () => openLink(context, l.shareUrl!),
                                icon: const Icon(Icons.ios_share_rounded, size: 17),
                                label: const Text('Partager'),
                              ),
                          ],
                        ),
                      ),
                    ),
                ]),
        ),
      ],
    );
  }
}
