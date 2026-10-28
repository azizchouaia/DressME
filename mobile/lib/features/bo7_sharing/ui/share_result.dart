// Owner: BO7 · M10 — a card made by the share agent: image, caption, channels, link, and "shop this look" (M7).
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/design/dressme_design.dart';
import '../data/bo7_models.dart';
import '../logic/bo7_providers.dart';
import 'widgets.dart';

const _channels = [
  ('whatsapp', 'WhatsApp', Color(0xFF1F8F55)),
  ('instagram', 'Instagram', Color(0xFFB13A73)),
  ('facebook', 'Facebook', Color(0xFF2D5DA8)),
  ('x', 'X', DmColors.inkDeep),
];

class ShareResult extends ConsumerWidget {
  const ShareResult({super.key, required this.card, this.pieces = const []});

  final ShareCard card;
  final List<Garment> pieces; // for "shop this look in Tunisia"

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final repo = ref.read(bo7RepositoryProvider);
    return Bo7Panel(
      title: 'Ta carte',
      trailing: TextButton.icon(
        onPressed: () => showPipeline(context, 'Agent share', card.pipeline),
        icon: const Icon(Icons.account_tree_outlined, size: 16),
        label: const Text('Voir le pipeline'),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(DmRadius.card),
            child: Container(
              color: DmColors.sand,
              constraints: const BoxConstraints(maxHeight: 520),
              child: Image.network(repo.url(card.imageUrl), fit: BoxFit.contain, semanticLabel: card.altText),
            ),
          ),
          const SizedBox(height: 10),
          Text(card.caption, style: DmText.body.copyWith(fontSize: 13, color: DmColors.text)),
          Text(card.captionSource == 'llm' ? 'Légende écrite par Llama 3.2 (RAG)' : 'Légende : modèle de texte',
              style: DmText.caption),
          const SizedBox(height: 14),
          const Text('PARTAGE-LA', style: DmText.eyebrow),
          const SizedBox(height: 6),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final (key, label, color) in _channels)
                FilledButton(
                  style: FilledButton.styleFrom(
                      backgroundColor: color, padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10)),
                  onPressed: () => openLink(context, card.channelLinks[key] ?? card.shareUrl),
                  child: Text(label),
                ),
              OutlinedButton.icon(
                onPressed: () async {
                  await Clipboard.setData(ClipboardData(text: card.shareUrl));
                  if (context.mounted) showSnack(context, 'Lien copié');
                },
                icon: const Icon(Icons.link, size: 16),
                label: const Text('Copier le lien'),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(color: DmColors.sand, borderRadius: BorderRadius.circular(DmRadius.card)),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                    'Tester comme une amie : ouvre la page qu\'elle voit, puis « Join DressMe ». '
                    'L\'ouverture et l\'inscription sont comptées pour le canal choisi.',
                    style: DmText.body),
                const SizedBox(height: 6),
                Wrap(
                  spacing: 6,
                  children: [
                    for (final (key, label, _) in _channels)
                      ActionChip(
                          label: Text('Page $label'), onPressed: () => openLink(context, repo.friendPage(card, key))),
                  ],
                ),
              ],
            ),
          ),
          if (pieces.isNotEmpty) ...[
            const SizedBox(height: 16),
            ShopTheLook(pieces: pieces),
          ],
        ],
      ),
    );
  }
}

/// "Acheter ce look en Tunisie": similar products of Tunisian shops and brands (M7), piece by piece.
class ShopTheLook extends ConsumerStatefulWidget {
  const ShopTheLook({super.key, required this.pieces});

  final List<Garment> pieces;

  @override
  ConsumerState<ShopTheLook> createState() => _ShopTheLookState();
}

class _ShopTheLookState extends ConsumerState<ShopTheLook> {
  late Future<List<LookMatch>> _future;

  @override
  void initState() {
    super.initState();
    _future = ref.read(bo7RepositoryProvider).shopTheLook(widget.pieces);
  }

  @override
  Widget build(BuildContext context) {
    final repo = ref.read(bo7RepositoryProvider);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Text('ACHETER CE LOOK EN TUNISIE · M7', style: DmText.eyebrow),
        const SizedBox(height: 6),
        FutureBuilder<List<LookMatch>>(
          future: _future,
          builder: (context, snap) {
            if (snap.connectionState != ConnectionState.done) {
              return const Padding(padding: EdgeInsets.all(12), child: LinearProgressIndicator());
            }
            final rows = (snap.data ?? const <LookMatch>[]).where((m) => m.products.isNotEmpty).toList();
            if (rows.isEmpty) return const Text('Aucun produit tunisien proche trouvé.', style: DmText.body);
            return Column(
              children: [
                for (final m in rows)
                  SizedBox(
                    height: 170,
                    child: ListView(
                      scrollDirection: Axis.horizontal,
                      children: [
                        for (final g in widget.pieces.where((g) => g.id == m.itemId))
                          SizedBox(width: 90, child: Padding(padding: const EdgeInsets.all(6), child: GarmentImage(g))),
                        for (final p in m.products)
                          InkWell(
                            onTap: p.url == null ? null : () => openLink(context, p.url!),
                            child: Container(
                              width: 140,
                              margin: const EdgeInsets.only(right: 8, bottom: 8),
                              padding: const EdgeInsets.all(8),
                              decoration: BoxDecoration(
                                color: DmColors.canvas,
                                borderRadius: BorderRadius.circular(DmRadius.card),
                                border: Border.all(color: DmColors.border),
                              ),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Expanded(
                                    child: ClipRRect(
                                      borderRadius: BorderRadius.circular(DmRadius.small),
                                      child: p.photo == null
                                          ? const ColoredBox(color: DmColors.sand, child: SizedBox.expand())
                                          : Image.network(repo.url(p.photo!),
                                              fit: BoxFit.cover,
                                              width: double.infinity,
                                              errorBuilder: (_, __, ___) => const ColoredBox(color: DmColors.sand)),
                                    ),
                                  ),
                                  const SizedBox(height: 4),
                                  Text(p.item,
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                      style: DmText.itemName.copyWith(fontSize: 11)),
                                  Text(
                                    '${p.shop}${p.priceTnd != null ? ' · ${p.priceTnd!.toStringAsFixed(p.priceTnd! % 1 == 0 ? 0 : 2)} DT' : ''}',
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: DmText.caption.copyWith(color: DmColors.bronze),
                                  ),
                                ],
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
              ],
            );
          },
        ),
      ],
    );
  }
}
