// One outfit of the user's own pieces, shown the same way on every screen (Home "Today", assistant,
// BO1/BO2, My style), with "See it on me" → the 3D avatar (BO9) wearing those pieces.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../api/dm_api.dart';
import '../design/dressme_design.dart';
import '../../features/bo7_sharing/ui/share_look.dart';

/// The user's pieces (id -> {name, image}) from /bo/catalog, loaded once per user.
final _catalogs = <String, Future<Map<String, Json>>>{};

Future<Map<String, Json>> userCatalog(DmApi api, String user) => _catalogs.putIfAbsent(user, () async {
      try {
        final c = await api.get('/bo/catalog', query: {'user_id': user});
        return {for (final e in ((c['pieces'] as Map?) ?? const {}).entries) '${e.key}': (e.value as Map).cast<String, dynamic>()};
      } catch (_) {
        _catalogs.remove(user);
        return <String, Json>{};
      }
    });

/// Forget the cached pieces (after adding / removing a piece).
void resetUserCatalog() => _catalogs.clear();

/// Item ids of the outfits found in any agent answer ({outfits: [{items | item_ids}]}, {item_ids}, ...).
List<List<String>> outfitIdsIn(Object? data) {
  final out = <List<String>>[];
  void visit(Object? v, int depth) {
    if (depth > 4 || v == null) return;
    if (v is Map) {
      final ids = v['item_ids'] ?? v['items'];
      if (ids is List && ids.isNotEmpty && ids.every((e) => e is String)) out.add([for (final e in ids) '$e']);
      for (final k in const ['outfits', 'result', 'data', 'outfit', 'looks']) {
        visit(v[k], depth + 1);
      }
    } else if (v is List) {
      for (final e in v.take(4)) {
        visit(e, depth + 1);
      }
    }
  }

  visit(data, 0);
  final seen = <String>{};
  return [for (final o in out) if (seen.add(o.join(','))) o];
}

void seeOnMe(BuildContext context, List<String> ids) => context.go('/bo9_avatar?wear=${Uri.encodeComponent(ids.join(','))}');

class OutfitStrip extends ConsumerWidget {
  const OutfitStrip({super.key, required this.ids, this.names = const [], this.size = 64, this.tryOn = true});

  final List<String> ids;
  final List<String> names;
  final double size;
  final bool tryOn;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final api = ref.read(dmApiProvider);
    return FutureBuilder<Map<String, Json>>(
      future: userCatalog(api, DemoUsers.wardrobe),
      builder: (context, snap) {
        final cat = snap.data ?? const <String, Json>{};
        return Wrap(spacing: 8, runSpacing: 8, crossAxisAlignment: WrapCrossAlignment.center, children: [
          for (final (i, id) in ids.indexed)
            SizedBox(
              width: size + 8,
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                Container(
                  width: size,
                  height: size,
                  padding: const EdgeInsets.all(4),
                  decoration: BoxDecoration(color: DmColors.page, borderRadius: BorderRadius.circular(12), border: Border.all(color: DmColors.border)),
                  child: (cat[id]?['image'] as String?)?.isNotEmpty == true
                      ? Image.network(api.media(cat[id]!['image'] as String), fit: BoxFit.contain,
                          errorBuilder: (_, __, ___) => const Icon(Icons.checkroom, color: DmColors.bronze))
                      : const Icon(Icons.checkroom, color: DmColors.bronze),
                ),
                const SizedBox(height: 3),
                Text('${cat[id]?['name'] ?? (i < names.length ? names[i] : 'piece')}',
                    style: DmText.caption, maxLines: 1, overflow: TextOverflow.ellipsis, textAlign: TextAlign.center),
              ]),
            ),
          if (tryOn && ids.isNotEmpty)
            OutlinedButton.icon(
              style: OutlinedButton.styleFrom(
                foregroundColor: DmColors.bronzeDark,
                side: const BorderSide(color: DmColors.gold),
                shape: const StadiumBorder(),
              ),
              onPressed: () => seeOnMe(context, ids),
              icon: const Icon(Icons.view_in_ar_outlined, size: 18),
              label: const Text('See it on me'),
            ),
          if (tryOn && ids.isNotEmpty) ShareLookButton(ids: ids),
        ]);
      },
    );
  }
}

/// Where a "next action" of an agent (its card's handoff: {tool, action, label, args}) opens in the app.
/// null = keep it in the chat (e.g. the stylist answers there).
String? routeForAction(Map a, {List<String> outfit = const []}) {
  final args = (a['args'] as Map?) ?? const {};
  String q(Map<String, Object?> p) => Uri(queryParameters: {
        for (final e in p.entries)
          if (e.value != null && '${e.value}'.isNotEmpty) e.key: '${e.value}'
      }).query;
  switch ('${a['tool'] ?? a['action'] ?? ''}') {
    case 'smartbuy' || 'judge' || 'should_i_buy':
      return '/bo5_smart_buy?${q({'type': args['subcategory'] ?? args['type'], 'colour': args['colour'] ?? args['color'], 'price': args['price_tnd'] ?? args['price']})}';
    case 'localshop' || 'local_shops' || 'find_in_shops':
      return '/bo6_local_market?${q({'q': args['query'] ?? [args['colour'] ?? args['color'], args['subcategory']].whereType<Object>().join(' ')})}';
    case 'share' || 'challenges':
      return '/bo7_sharing';
    case 'taste' || 'profile':
      return '/my_style';
    case 'tryon' || 'try_on':
      return outfit.isEmpty ? '/bo9_avatar' : '/bo9_avatar?wear=${Uri.encodeComponent(outfit.join(','))}';
    case 'wardrobe':
      return '/bo4_style';
  }
  return null;
}
