// Owner: BO7 (Amenallah) — "Share this look" from anywhere in the app (Today, BO1/BO2 outfits, assistant,
// My style, the 3D avatar): the outfit's pieces go to M10 (POST /m10/cards, Amenallah's share agent) and his
// card (image, caption, channels, link) opens in a sheet.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/dm_api.dart';
import '../../../core/design/dressme_design.dart';
import '../data/bo7_models.dart';
import '../logic/bo7_providers.dart';
import 'share_result.dart';

Future<void> shareLook(BuildContext context, WidgetRef ref, List<String> ids, {String? title, String kind = 'outfit'}) async {
  final repo = ref.read(bo7RepositoryProvider);
  final messenger = ScaffoldMessenger.of(context);
  messenger.showSnackBar(const SnackBar(content: Text('Making your share card…')));
  try {
    final all = await repo.wardrobe(DemoUsers.wardrobe);
    final pieces = [for (final id in ids) ...all.where((g) => g.id == id)];
    if (pieces.isEmpty) throw Exception('these pieces are not in your wardrobe');
    final card = await repo.createCard(
      userId: DemoUsers.wardrobe,
      kind: kind,
      pieces: pieces,
      title: title ?? 'My look',
      language: 'en',
    );
    messenger.hideCurrentSnackBar();
    if (!context.mounted) return;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      backgroundColor: DmColors.page,
      builder: (_) => DraggableScrollableSheet(
        expand: false,
        initialChildSize: .9,
        builder: (_, controller) => ListView(
          controller: controller,
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
          children: [ShareResult(card: card, pieces: pieces)],
        ),
      ),
    );
  } catch (e) {
    messenger
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text('Could not make the card: ${e is Exception ? '$e'.replaceFirst('Exception: ', '') : apiError(e)}')));
  }
}

/// Small button used next to "See it on me".
class ShareLookButton extends ConsumerWidget {
  const ShareLookButton({super.key, required this.ids, this.title});

  final List<String> ids;
  final String? title;

  @override
  Widget build(BuildContext context, WidgetRef ref) => TextButton.icon(
        onPressed: ids.isEmpty ? null : () => shareLook(context, ref, ids, title: title),
        icon: const Icon(Icons.ios_share_rounded, size: 18),
        label: const Text('Share this look'),
      );
}

/// Garment ids helper for screens that only have the BO7 models.
List<String> idsOf(List<Garment> g) => [for (final x in g) x.id];
