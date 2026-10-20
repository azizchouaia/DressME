// Owner: BO7 · M15 — pick today's pieces from the wardrobe (M1) and submit them.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/challenge_models.dart';
import '../logic/challenges_providers.dart';
import 'widgets.dart';

class OutfitSelection {
  const OutfitSelection(this.itemIds, this.caption);
  final List<String> itemIds;
  final String caption;
}

const _order = ['outerwear', 'top', 'dress', 'traditional', 'bottom', 'shoes', 'accessory'];
const _labels = {
  'outerwear': 'Outerwear',
  'top': 'Tops',
  'dress': 'Dresses',
  'traditional': 'Traditional',
  'bottom': 'Bottoms',
  'shoes': 'Shoes',
  'accessory': 'Accessories',
};

Future<OutfitSelection?> showOutfitPicker(BuildContext context, {required int day, List<String> preselect = const []}) {
  return showModalBottomSheet<OutfitSelection>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (_) => FractionallySizedBox(
      heightFactor: 0.9,
      child: OutfitPicker(day: day, preselect: preselect),
    ),
  );
}

class OutfitPicker extends ConsumerStatefulWidget {
  const OutfitPicker({super.key, required this.day, this.preselect = const []});
  final int day;
  final List<String> preselect;

  @override
  ConsumerState<OutfitPicker> createState() => _OutfitPickerState();
}

class _OutfitPickerState extends ConsumerState<OutfitPicker> {
  late final Set<String> _selected = {...widget.preselect};
  final _caption = TextEditingController();

  @override
  void dispose() {
    _caption.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final wardrobe = ref.watch(wardrobeProvider);
    return wardrobe.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text('$e')),
      data: (items) {
        final groups = <String, List<WardrobeItem>>{};
        for (final it in items) {
          groups.putIfAbsent(it.category, () => []).add(it);
        }
        final cats = _order.where(groups.containsKey).toList();
        return Column(
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Row(children: [
                Text('Day ${widget.day} · what did you wear?', style: Theme.of(context).textTheme.titleMedium),
                const Spacer(),
                Text('${_selected.length} selected'),
              ]),
            ),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.symmetric(vertical: 8),
                children: [
                  for (final cat in cats) ...[
                    Padding(
                      padding: const EdgeInsets.fromLTRB(20, 12, 20, 6),
                      child: Text(_labels[cat] ?? cat, style: Theme.of(context).textTheme.labelLarge),
                    ),
                    SizedBox(
                      height: 112,
                      child: ListView.separated(
                        scrollDirection: Axis.horizontal,
                        padding: const EdgeInsets.symmetric(horizontal: 20),
                        itemCount: groups[cat]!.length,
                        separatorBuilder: (_, __) => const SizedBox(width: 8),
                        itemBuilder: (_, i) {
                          final it = groups[cat]![i];
                          final sel = _selected.contains(it.id);
                          return GarmentChip(
                            item: it,
                            selected: sel,
                            onTap: () => setState(() => sel ? _selected.remove(it.id) : _selected.add(it.id)),
                          );
                        },
                      ),
                    ),
                  ],
                ],
              ),
            ),
            SafeArea(
              top: false,
              child: Padding(
                padding: EdgeInsets.fromLTRB(20, 8, 20, 12 + MediaQuery.viewInsetsOf(context).bottom),
                child: Column(children: [
                  TextField(
                    controller: _caption,
                    decoration: const InputDecoration(
                      labelText: 'Caption (optional)',
                      border: OutlineInputBorder(),
                      isDense: true,
                    ),
                  ),
                  const SizedBox(height: 8),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      onPressed: _selected.isEmpty
                          ? null
                          : () => Navigator.pop(context, OutfitSelection(_selected.toList(), _caption.text.trim())),
                      child: const Text('Check my outfit'),
                    ),
                  ),
                ]),
              ),
            ),
          ],
        );
      },
    );
  }
}
