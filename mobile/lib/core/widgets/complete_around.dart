// "Build an outfit around this piece": the user picks one of their pieces, M2 (Racem) completes the outfit
// around it (pinned piece, the rest chosen from the same wardrobe, the weather and the M5 taste).
// Used in the Wardrobe piece sheet (BO4) and the Outfits screen (BO1).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/dm_api.dart';
import '../design/dressme_design.dart';
import 'dm_motion.dart';
import 'dm_widgets.dart';
import 'outfit_strip.dart';

const _occasions = {'casual': 'Casual', 'work': 'Work', 'event': 'Event', 'sport': 'Sport'};
const _moods = {null: 'Any mood', 'comfy': 'Comfy', 'classy': 'Classy', 'bold': 'Bold'};

Future<void> showCompleteAround(BuildContext context, String pieceId, {String? pieceName}) => showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      backgroundColor: DmColors.page,
      builder: (_) => DraggableScrollableSheet(
        expand: false,
        initialChildSize: .85,
        maxChildSize: .95,
        builder: (_, controller) => _CompleteAround(pieceId: pieceId, pieceName: pieceName, controller: controller),
      ),
    );

class _CompleteAround extends ConsumerStatefulWidget {
  const _CompleteAround({required this.pieceId, required this.controller, this.pieceName});

  final String pieceId;
  final String? pieceName;
  final ScrollController controller;

  @override
  ConsumerState<_CompleteAround> createState() => _CompleteAroundState();
}

class _CompleteAroundState extends ConsumerState<_CompleteAround> {
  String occasion = 'casual';
  String? mood;
  bool loading = true;
  String? error;
  List<(List<String>, double?)> outfits = const [];
  final seen = <String>{}; // pieces already proposed: "Other ideas" avoids them
  final worn = <String>{};

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load({bool more = false}) async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final r = await ref.read(dmApiProvider).call('/m02/complete', userId: DemoUsers.outfits, payload: {
        'pinned_item_ids': [widget.pieceId],
        'context': {'occasion': occasion, if (mood != null) 'mood': mood},
        'options': {'n': 3, if (more) 'exclude_item_ids': seen.where((id) => id != widget.pieceId).toList()},
      });
      final list = <(List<String>, double?)>[
        for (final o in jsonList(r['outfits']))
          ([for (final i in (o['items'] ?? o['item_ids'] ?? const []) as List) '$i'], (o['score'] as num?)?.toDouble()),
      ].where((o) => o.$1.isNotEmpty).toList();
      for (final o in list) {
        seen.addAll(o.$1);
      }
      setState(() => outfits = list);
    } catch (e) {
      setState(() => error = apiError(e));
    }
    if (mounted) setState(() => loading = false);
  }

  Future<void> _wear(List<String> ids) async {
    try {
      await ref.read(dmApiProvider).call('/m03/worn', userId: DemoUsers.outfits, payload: {'item_ids': ids, 'source': 'suggestion'});
      setState(() => worn.add(ids.join(',')));
      if (mounted) dmToast(context, 'Logged as worn today. Enjoy!');
    } catch (e) {
      if (mounted) dmToast(context, apiError(e));
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListView(controller: widget.controller, padding: const EdgeInsets.fromLTRB(20, 0, 20, 28), children: [
      const Text('BUILD AROUND THIS PIECE', style: DmText.eyebrow),
      const SizedBox(height: 4),
      Text('Outfits with your ${widget.pieceName ?? 'piece'}', style: DmText.title),
      const SizedBox(height: 10),
      Container(
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(DmRadius.card), border: Border.all(color: DmColors.gold)),
        child: Row(children: [
          OutfitStrip(ids: [widget.pieceId], size: 56, tryOn: false),
          const SizedBox(width: 10),
          const Expanded(child: Text('Your piece stays. The stylist completes the rest from your wardrobe, the weather and your style.',
              style: DmText.caption)),
        ]),
      ),
      const SizedBox(height: 14),
      Wrap(spacing: 6, runSpacing: 6, children: [
        for (final e in _occasions.entries)
          DmChoiceChip(label: e.value, selected: occasion == e.key, onTap: () {
            setState(() => occasion = e.key);
            _load();
          }),
      ]),
      const SizedBox(height: 6),
      Wrap(spacing: 6, runSpacing: 6, children: [
        for (final e in _moods.entries)
          DmChoiceChip(label: e.value, selected: mood == e.key, onTap: () {
            setState(() => mood = e.key);
            _load();
          }),
      ]),
      const SizedBox(height: 16),
      if (loading)
        const DmSkeleton(cards: 3)
      else if (error != null)
        DmEmptyState(icon: Icons.wifi_off_rounded, title: 'No outfit right now', message: error!, action: DmButton('Try again', onPressed: _load))
      else if (outfits.isEmpty)
        const DmEmptyState(
          icon: Icons.checkroom_outlined,
          title: 'Not enough pieces to match it',
          message: 'Add a few more pieces (a top, a bottom, shoes) in your Wardrobe, then try again.',
        )
      else ...[
        for (final (i, o) in outfits.indexed)
          DmAppear(
            index: i,
            child: Container(
              margin: const EdgeInsets.only(bottom: 12),
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(DmRadius.panel),
                border: Border.all(color: DmColors.border),
                boxShadow: const [BoxShadow(color: Color(0x0F000000), blurRadius: 12, offset: Offset(0, 4))],
              ),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  Text(i == 0 ? 'BEST MATCH' : 'IDEA ${i + 1}', style: DmText.eyebrow),
                  const Spacer(),
                  if (o.$2 != null)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                      decoration: BoxDecoration(color: DmColors.sandDark, borderRadius: BorderRadius.circular(DmRadius.pill)),
                      child: Text('${(o.$2! * 100).round()} % match', style: DmText.caption.copyWith(fontWeight: FontWeight.w700)),
                    ),
                ]),
                const SizedBox(height: 10),
                OutfitStrip(ids: o.$1, size: 64),
                const SizedBox(height: 4),
                Align(
                  alignment: Alignment.centerLeft,
                  child: worn.contains(o.$1.join(','))
                      ? const Chip(avatar: Icon(Icons.check_circle, size: 16, color: DmColors.success), label: Text('Worn today'))
                      : TextButton.icon(
                          onPressed: () => _wear(o.$1),
                          icon: const Icon(Icons.check_rounded, size: 18),
                          label: const Text('I wear it today'),
                        ),
                ),
              ]),
            ),
          ),
        DmButton('Other ideas', kind: DmButtonKind.outline, icon: Icons.refresh_rounded, onPressed: () => _load(more: true)),
      ],
    ]);
  }
}

/// "Start from one of my pieces": the wardrobe in a row; tap a piece to build around it.
class PiecePicker extends ConsumerWidget {
  const PiecePicker({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final api = ref.read(dmApiProvider);
    return DmCard(
      padding: const EdgeInsets.all(14),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Expanded(child: Text('Start from one of my pieces', style: DmText.cardTitle)),
          Text('BO1 · M2 complete', style: DmText.caption.copyWith(color: DmColors.bronze, fontWeight: FontWeight.w700)),
        ]),
        const Text('Pick a piece: I complete the outfit around it.', style: DmText.caption),
        const SizedBox(height: 10),
        SizedBox(
          height: 112,
          child: FutureBuilder<Map<String, Json>>(
            future: userCatalog(api, DemoUsers.wardrobe),
            builder: (context, snap) {
              if (!snap.hasData) return const Center(child: CircularProgressIndicator());
              final pieces = snap.data!.entries.toList();
              if (pieces.isEmpty) {
                return const Center(child: Text('Your wardrobe is empty: add pieces in Wardrobe.', style: DmText.caption));
              }
              return ListView(scrollDirection: Axis.horizontal, children: [
                for (final (i, e) in pieces.indexed)
                  DmAppear(
                    index: i,
                    child: DmPressable(
                      onTap: () {},
                      child: GestureDetector(
                        onTap: () => showCompleteAround(context, e.key, pieceName: '${e.value['name'] ?? 'piece'}'),
                        child: Container(
                          width: 84,
                          margin: const EdgeInsets.only(right: 8),
                          padding: const EdgeInsets.all(6),
                          decoration: BoxDecoration(
                            color: DmColors.page,
                            borderRadius: BorderRadius.circular(DmRadius.card),
                            border: Border.all(color: DmColors.border),
                          ),
                          child: Column(children: [
                            Expanded(
                              child: (e.value['image'] as String?)?.isNotEmpty == true
                                  ? Image.network(api.media(e.value['image'] as String), fit: BoxFit.contain,
                                      errorBuilder: (_, __, ___) => const Icon(Icons.checkroom, color: DmColors.bronze))
                                  : const Icon(Icons.checkroom, color: DmColors.bronze),
                            ),
                            const SizedBox(height: 4),
                            Text('${e.value['name'] ?? ''}', maxLines: 1, overflow: TextOverflow.ellipsis, style: DmText.caption),
                          ]),
                        ),
                      ),
                    ),
                  ),
              ]);
            },
          ),
        ),
      ]),
    );
  }
}
