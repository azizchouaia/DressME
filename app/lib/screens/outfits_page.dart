import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../garments.dart';
import '../models.dart';
import '../state.dart';
import '../theme.dart';
import '../widgets/ui.dart';

class OutfitsPage extends ConsumerWidget {
  const OutfitsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final outfits = ref.watch(outfitsProvider);
    final items = ref.watch(wardrobeProvider).value ?? const <ClothingItem>[];
    final byId = {for (final item in items) item.id: item};
    final list = outfits.value ?? const <Outfit>[];

    return PageFrame(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          PageHeader(
            title: 'Outfits',
            subtitle: outfits.isLoading && list.isEmpty ? 'Loading…' : '${list.length} saved',
            action: FilledButton.tonal(onPressed: () => context.go('/avatar'), child: const Text('New')),
          ),
          Expanded(child: _body(context, ref, outfits, list, byId)),
        ],
      ),
    );
  }

  Widget _body(
    BuildContext context,
    WidgetRef ref,
    AsyncValue<List<Outfit>> outfits,
    List<Outfit> list,
    Map<String, ClothingItem> byId,
  ) {
    if (outfits.hasError && list.isEmpty) {
      return StatusMessage(message: outfits.error.toString(), onRetry: () => ref.read(outfitsProvider.notifier).reload());
    }
    if (outfits.isLoading && list.isEmpty) return const Center(child: CircularProgressIndicator());
    if (list.isEmpty) {
      return EmptyPanel(
        title: 'No outfits yet',
        text: 'Dress your avatar and save the look to find it here.',
        action: PrimaryButton(label: 'Dress your avatar', onPressed: () => context.go('/avatar')),
      );
    }
    return ListView.separated(
      itemCount: list.length,
      separatorBuilder: (_, _) => const SizedBox(height: 12),
      itemBuilder: (context, index) {
        final outfit = list[index];
        final pieces = [
          for (final field in const ['shirt_id', 'pants_id', 'jacket_id', 'shoes_id'])
            if (slotField(outfit, field) != null) byId[slotField(outfit, field)],
        ].whereType<ClothingItem>().toList();
        return Card(
          child: InkWell(
            onTap: () => context.go('/avatar?outfit=${outfit.id}'),
            borderRadius: BorderRadius.circular(24),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  SizedBox(
                    width: 132,
                    height: 64,
                    child: pieces.isEmpty
                        ? const Align(alignment: Alignment.centerLeft, child: Text('No items', style: TextStyle(color: muted)))
                        : ListView.separated(
                            scrollDirection: Axis.horizontal,
                            itemCount: pieces.length,
                            separatorBuilder: (_, _) => const SizedBox(width: 6),
                            itemBuilder: (_, index) => ClothingThumb(item: pieces[index], size: 64),
                          ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(outfit.name, style: const TextStyle(fontWeight: FontWeight.w600)),
                        Text(
                          pieces.isEmpty ? 'Empty outfit' : pieces.map((piece) => piece.name).join(' · '),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(color: muted, fontSize: 13),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    tooltip: 'Delete ${outfit.name}',
                    onPressed: () => _delete(context, ref, outfit),
                    icon: const Icon(Icons.delete_outline),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Future<void> _delete(BuildContext context, WidgetRef ref, Outfit outfit) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete outfit?'),
        content: Text('Delete “${outfit.name}”?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          TextButton(onPressed: () => Navigator.pop(context, true), child: const Text('Delete')),
        ],
      ),
    );
    if (confirmed != true) return;
    await ref.read(apiProvider).deleteOutfit(outfit.id);
    ref.read(outfitsProvider.notifier).removeLocal(outfit.id);
    if (ref.read(outfitEditorProvider).outfit?.id == outfit.id) {
      ref.read(outfitEditorProvider.notifier).startNew(ref.read(outfitEditorProvider).selection);
    }
  }
}
