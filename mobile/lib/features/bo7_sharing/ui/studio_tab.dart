// Owner: BO7 · M10 — "Studio": share my own outfits as a card, see which channel brings new users.
// Card types: outfit of the day, my look (board), give-away, and "on my avatar" (BO9 avatar, M9).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/design/dressme_design.dart';
import '../data/bo7_models.dart';
import '../data/bo7_repository.dart';
import '../logic/bo7_providers.dart';
import 'avatar_share_screen.dart';
import 'share_result.dart';
import 'widgets.dart';

class CardKind {
  const CardKind(this.kind, this.label, this.hint, this.title,
      {this.format = 'story', this.min = 1, this.max = 8, this.outfit = false});
  final String kind;
  final String label;
  final String hint;
  final String title;
  final String format;
  final int min;
  final int max;
  final bool outfit; // a wearable outfit: a top and a bottom, or a one-piece (dress, jebba)
}

const cardKinds = [
  CardKind('outfit', 'Tenue du jour', 'story 1080×1920', 'Ma tenue du jour', outfit: true),
  CardKind('board', 'Mon look', 'carré pour Instagram', 'Mon look', format: 'square'),
  CardKind('giveaway', 'Je donne', 'une pièce que je ne porte plus', 'Je la donne', format: 'post', max: 1),
  CardKind('tryon', 'Sur mon avatar', 'avatar 3D (BO9), sans selfie', 'Mon look sur mon avatar'),
];

const languages = {'fr': 'Français', 'en': 'English', 'tn': 'Derja (tounsi)'};

class StudioTab extends ConsumerStatefulWidget {
  const StudioTab({super.key});

  @override
  ConsumerState<StudioTab> createState() => _StudioTabState();
}

class _StudioTabState extends ConsumerState<StudioTab> {
  final Set<String> _picked = {};
  CardKind _kind = cardKinds.first;
  String _lang = 'fr';
  bool _qr = false;
  String? _shop;
  bool _busy = false;
  ShareCard? _card;
  List<Garment> _cardPieces = const [];
  bool _mine = false;

  List<Garment> _pieces(List<Garment> ward) => [for (final id in _picked) ...ward.where((g) => g.id == id)];

  /// if/else like the agent: a top and a bottom, or a one-piece.
  static bool _wearable(List<Garment> pieces) {
    bool has(Set<String> cats) => pieces.any((g) => cats.contains(g.category));
    return has({'dress', 'traditional'}) || (has({'top', 'outerwear'}) && has({'bottom'}));
  }

  Future<void> _make(List<Garment> ward) async {
    final pieces = _pieces(ward);
    if (_kind.outfit && !_wearable(pieces)) {
      showSnack(context, '${_kind.label} : choisis un haut et un bas, ou une pièce unique (robe, jebba).');
      return;
    }
    if (pieces.length < _kind.min || pieces.length > _kind.max) {
      showSnack(
        context,
        _kind.max == 1 ? 'Choisis une seule pièce pour « ${_kind.label} ».' : 'Choisis au moins ${_kind.min} pièce(s).',
      );
      return;
    }
    if (_kind.kind == 'tryon') {
      final card = await Navigator.of(context).push<ShareCard>(
        MaterialPageRoute(
          builder: (_) => Theme(
            data: dressMeTheme(),
            child: AvatarShareScreen(pieces: pieces, language: _lang, qr: _qr, shop: _shop),
          ),
        ),
      );
      if (card != null) {
        setState(() {
          _card = card;
          _cardPieces = pieces;
        });
        ref.invalidate(metricsProvider);
        ref.invalidate(ambassadorsProvider);
      }
      return;
    }
    setState(() => _busy = true);
    try {
      final card = await ref.read(bo7RepositoryProvider).createCard(
            userId: ref.read(currentUserProvider),
            kind: _kind.kind,
            pieces: pieces,
            title: _kind.title,
            subtitle: _shop != null ? 'Stylé avec $_shop' : (_kind.kind == 'giveaway' ? 'Bon état, Tunis' : 'Tunis'),
            format: _kind.format,
            language: _lang,
            qr: _qr,
          );
      setState(() {
        _card = card;
        _cardPieces = pieces;
      });
      ref.invalidate(metricsProvider);
      ref.invalidate(ambassadorsProvider);
    } on Bo7Exception catch (e) {
      if (mounted) showSnack(context, e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final ward = ref.watch(wardrobeProvider);
    final shops = ref.watch(shopsProvider).valueOrNull ?? const <Shop>[];
    final user = ref.watch(currentUserProvider);
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
      children: [
        const Bo7Hero(
          eyebrow: 'Studio · M10 cartes de partage',
          title: 'Partager mon look',
          subtitle: 'Choisis tes pièces, une carte, partage-la sur un canal, puis vois quel canal amène de nouveaux '
              'utilisateurs. La carte n\'invente jamais une tenue.',
        ),
        const SizedBox(height: 16),
        Bo7Panel(
          title: '1. Choisis tes pièces',
          subtitle: 'La carte montre tes propres vêtements (M1).',
          child: AsyncBody<List<Garment>>(
            value: ward,
            onRetry: () => ref.invalidate(wardrobeProvider),
            builder: (items) => Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                GarmentPicker(
                  garments: items,
                  selected: _picked,
                  onToggle: (g) => setState(() => _picked.contains(g.id) ? _picked.remove(g.id) : _picked.add(g.id)),
                ),
                const SizedBox(height: 6),
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        _picked.isEmpty
                            ? 'Aucune pièce choisie.'
                            : 'Tes pièces : ${_pieces(items).map((g) => g.name).join(', ')}',
                        style: DmText.caption,
                      ),
                    ),
                    if (_picked.isNotEmpty)
                      TextButton(onPressed: () => setState(_picked.clear), child: const Text('Effacer')),
                  ],
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 14),
        Bo7Panel(
          title: '2. Choisis la carte',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final k in cardKinds)
                    _KindButton(kind: k, selected: k == _kind, onTap: () => setState(() => _kind = k))
                ],
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 12,
                runSpacing: 8,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  DropdownButton<String>(
                    value: _lang,
                    underline: const SizedBox(),
                    items: [
                      for (final e in languages.entries)
                        DropdownMenuItem(value: e.key, child: Text('Légende : ${e.value}'))
                    ],
                    onChanged: (v) => setState(() => _lang = v ?? 'fr'),
                  ),
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Switch(value: _qr, onChanged: (v) => setState(() => _qr = v)),
                      const Text('QR code sur la carte', style: DmText.itemName),
                    ],
                  ),
                  if (shops.isNotEmpty)
                    DropdownButton<String?>(
                      value: _shop,
                      underline: const SizedBox(),
                      hint: const Text('Taguer une boutique tunisienne'),
                      items: [
                        const DropdownMenuItem<String?>(value: null, child: Text('Aucune boutique')),
                        for (final s in shops) DropdownMenuItem<String?>(value: s.name, child: Text(s.name)),
                      ],
                      onChanged: (v) => setState(() => _shop = v),
                    ),
                ],
              ),
              const SizedBox(height: 12),
              FilledButton.icon(
                onPressed: _busy || ward.valueOrNull == null ? null : () => _make(ward.value!),
                icon: Icon(_kind.kind == 'tryon' ? Icons.accessibility_new_rounded : Icons.auto_awesome, size: 18),
                label: Text(_busy
                    ? 'Dessin de la carte…'
                    : (_kind.kind == 'tryon' ? 'Continuer avec mon avatar' : 'Créer la carte')),
              ),
            ],
          ),
        ),
        if (_card != null) ...[
          const SizedBox(height: 14),
          ShareResult(key: ValueKey(_card!.cardId), card: _card!, pieces: _cardPieces),
        ],
        const SizedBox(height: 14),
        Bo7Panel(
          title: 'Nouveaux utilisateurs via le partage',
          trailing: IconButton(
            tooltip: 'Actualiser',
            icon: const Icon(Icons.refresh),
            onPressed: () {
              ref.invalidate(metricsProvider);
              ref.invalidate(ambassadorsProvider);
            },
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  Switch(value: _mine, onChanged: (v) => setState(() => _mine = v)),
                  Text('Seulement $user', style: DmText.itemName),
                ],
              ),
              AsyncBody<ShareMetrics>(
                value: ref.watch(metricsProvider(_mine ? user : null)),
                compact: true,
                builder: (m) => Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        StatTile('${m.cards}', 'cartes'),
                        StatTile('${m.opens}', 'liens ouverts'),
                        StatTile('${m.signups}', 'inscriptions'),
                        StatTile(m.kFactor.toStringAsFixed(2), 'K-factor', dark: true),
                      ],
                    ),
                    const SizedBox(height: 8),
                    const Text(
                        'K-factor = cartes par personne × ouvertures par carte × inscriptions par ouverture. '
                        'Au-dessus de 1, chaque utilisatrice en amène plus d\'une.',
                        style: DmText.caption),
                    const SizedBox(height: 12),
                    const Text('PAR CANAL', style: DmText.eyebrow),
                    const SizedBox(height: 4),
                    if (m.channels.isEmpty)
                      const Text('Aucun lien ouvert pour l\'instant.', style: DmText.body)
                    else
                      for (final c in m.channels)
                        Padding(
                          padding: const EdgeInsets.symmetric(vertical: 3),
                          child: Row(
                            children: [
                              SizedBox(width: 90, child: Text(c.channel, style: DmText.itemName)),
                              Expanded(
                                child: ClipRRect(
                                  borderRadius: BorderRadius.circular(4),
                                  child: LinearProgressIndicator(
                                    value: m.opens == 0 ? 0 : c.opens / m.opens,
                                    minHeight: 6,
                                  ),
                                ),
                              ),
                              const SizedBox(width: 8),
                              Text('${c.opens} ouv. · ${c.signups} insc.', style: DmText.caption),
                            ],
                          ),
                        ),
                  ],
                ),
              ),
              const SizedBox(height: 12),
              const Text('AMBASSADEURS', style: DmText.eyebrow),
              const SizedBox(height: 4),
              AsyncBody<List<Ambassador>>(
                value: ref.watch(ambassadorsProvider),
                compact: true,
                builder: (rows) => rows.isEmpty
                    ? const Text('Personne pour l\'instant.', style: DmText.body)
                    : Column(
                        children: [
                          for (final a in rows.take(5))
                            ListTile(
                              dense: true,
                              contentPadding: EdgeInsets.zero,
                              leading: UserAvatar(a.userId, radius: 14),
                              title: Text('${a.rank}. ${a.userId}', style: DmText.itemName),
                              subtitle: Text('${a.signups} inscription(s) · ${a.points} points', style: DmText.caption),
                              trailing: a.tier == null ? null : DmPill(a.tier!, dark: true),
                            ),
                        ],
                      ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _KindButton extends StatelessWidget {
  const _KindButton({required this.kind, required this.selected, required this.onTap});

  final CardKind kind;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final avatar = kind.kind == 'tryon';
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(DmRadius.card),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 160),
        width: 165,
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: selected ? DmColors.ink : (avatar ? DmColors.sand : DmColors.surface),
          borderRadius: BorderRadius.circular(DmRadius.card),
          border: Border.all(color: selected ? DmColors.ink : DmColors.border),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                if (avatar) Icon(Icons.view_in_ar_rounded, size: 15, color: selected ? DmColors.gold : DmColors.bronze),
                if (avatar) const SizedBox(width: 4),
                Flexible(
                  child: Text(kind.label,
                      style: DmText.itemName.copyWith(fontSize: 13, color: selected ? Colors.white : DmColors.ink)),
                ),
              ],
            ),
            const SizedBox(height: 2),
            Text(kind.hint, style: DmText.caption.copyWith(color: selected ? Colors.white60 : DmColors.muted)),
          ],
        ),
      ),
    );
  }
}
