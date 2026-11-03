import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../garments.dart';
import '../models.dart';
import '../state.dart';
import '../theme.dart';
import '../widgets/ui.dart';

class WardrobePage extends ConsumerStatefulWidget {
  const WardrobePage({super.key});

  @override
  ConsumerState<WardrobePage> createState() => _WardrobePageState();
}

class _WardrobePageState extends ConsumerState<WardrobePage> {
  var _filter = 'all';

  @override
  Widget build(BuildContext context) {
    final wardrobe = ref.watch(wardrobeProvider);
    final items = wardrobe.value ?? const <ClothingItem>[];
    final counts = <String, int>{'all': items.length};
    for (final item in items) {
      counts[item.category] = (counts[item.category] ?? 0) + 1;
    }
    final options = [
      for (final filter in categoryFilters)
        if (filter.$1 == 'all' || counts.containsKey(filter.$1)) (filter.$1, '${filter.$2} ${counts[filter.$1] ?? 0}'),
    ];
    final visible = _filter == 'all' ? items : items.where((item) => item.category == _filter).toList();

    return PageFrame(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          PageHeader(
            title: 'Wardrobe',
            subtitle: wardrobe.isLoading && items.isEmpty ? 'Loading…' : '${items.length} pieces',
            action: FilledButton.tonal(
              onPressed: () => context.push('/wardrobe/add'),
              child: const Text('Add'),
            ),
          ),
          if (items.isNotEmpty) ...[
            ChoiceChips(options: options, value: _filter, onChanged: (value) => setState(() => _filter = value)),
            const SizedBox(height: 16),
          ],
          Expanded(child: _body(wardrobe, items, visible)),
        ],
      ),
    );
  }

  Widget _body(AsyncValue<List<ClothingItem>> wardrobe, List<ClothingItem> items, List<ClothingItem> visible) {
    if (wardrobe.hasError && items.isEmpty) {
      return StatusMessage(message: wardrobe.error.toString(), onRetry: () => ref.read(wardrobeProvider.notifier).reload());
    }
    if (wardrobe.isLoading && items.isEmpty) return const Center(child: CircularProgressIndicator());
    if (visible.isEmpty) {
      return EmptyPanel(
        title: items.isEmpty ? 'Your wardrobe is empty' : 'Nothing in this category',
        text: 'Snap a photo of something you own to add it.',
        action: PrimaryButton(label: 'Add clothing', onPressed: () => context.push('/wardrobe/add')),
      );
    }
    return GridView.builder(
      gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
        maxCrossAxisExtent: 220,
        mainAxisSpacing: 12,
        crossAxisSpacing: 12,
        childAspectRatio: 0.72,
      ),
      itemCount: visible.length,
      itemBuilder: (context, index) => _ClothingCard(item: visible[index]),
    );
  }
}

class _ClothingCard extends StatelessWidget {
  const _ClothingCard({required this.item});

  final ClothingItem item;

  @override
  Widget build(BuildContext context) {
    final extras = [item.brand, if (item.size != null && item.size!.isNotEmpty) 'Size ${item.size}'].whereType<String>().join(' · ');
    return InkWell(
      onTap: () => context.push('/wardrobe/${item.id}'),
      borderRadius: BorderRadius.circular(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Stack(
            children: [
              ClothingThumb(item: item, size: null),
              if (item.glbUrl != null)
                const Positioned(
                  top: 8,
                  left: 8,
                  child: DecoratedBox(
                    decoration: BoxDecoration(color: surface, borderRadius: BorderRadius.all(Radius.circular(999))),
                    child: Padding(
                      padding: EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      child: Text('3D', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700)),
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 8),
          Text(item.name, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600)),
          Text(describeItem(item), maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: muted, fontSize: 13)),
          if (extras.isNotEmpty)
            Text(extras, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: muted, fontSize: 12)),
        ],
      ),
    );
  }
}
