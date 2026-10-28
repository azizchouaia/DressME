// Owner: BO4 (Amine) — my wardrobe (M1: photo -> piece) and my style profile (M5). Integration screen.
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../../core/api/dm_api.dart';
import '../../../core/design/dressme_design.dart';
import '../../../core/widgets/dm_async.dart';
import '../../../core/widgets/dm_widgets.dart';

class StyleProfileScreen extends ConsumerStatefulWidget {
  const StyleProfileScreen({super.key});

  @override
  ConsumerState<StyleProfileScreen> createState() => _StyleProfileScreenState();
}

class _StyleProfileScreenState extends ConsumerState<StyleProfileScreen> {
  int _run = 0;
  bool _adding = false;
  String? _category;

  DmApi get _api => ref.read(dmApiProvider);

  Future<void> _add(ImageSource source) async {
    final file = await ImagePicker().pickImage(source: source, maxWidth: 1000, imageQuality: 85);
    if (file == null) return;
    setState(() => _adding = true);
    try {
      final bytes = await file.readAsBytes();
      final r = await _api.post('/m01/classify', {
        'user_id': DemoUsers.wardrobe,
        'image': 'data:image/jpeg;base64,${base64Encode(bytes)}',
        'mode': 'add_to_wardrobe',
        'on_duplicate': 'ask',
      });
      final g = ((r['garment'] as Map?) ?? const {}).cast<String, dynamic>();
      final label = _label(g);
      if (r['pending'] == true) {
        // M1 found a piece that looks the same: it waits (hidden) until the user decides
        final keep = await _askDuplicate(g, jsonList(r['duplicates']));
        final id = g['item_id'];
        if (keep == true) {
          await _api.post('/m01/items/$id/confirm?user_id=${DemoUsers.wardrobe}');
          if (mounted) dmToast(context, 'Added anyway: $label');
        } else {
          await _api.delete('/m01/items/$id', query: {'user_id': DemoUsers.wardrobe});
          if (mounted) dmToast(context, 'Not added: you already have it');
        }
      } else if (mounted) {
        dmToast(context, r['needs_confirmation'] == true ? 'Added: $label (check the details, the AI was not sure)' : 'Added: $label');
      }
      if (mounted) setState(() => _run++);
    } catch (e) {
      if (mounted) dmToast(context, apiError(e));
    } finally {
      if (mounted) setState(() => _adding = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return DmPage(
      eyebrow: 'BO4 · My style',
      title: 'My wardrobe',
      heroChild: Row(children: [
        Expanded(
          child: DmButton(_adding ? 'Reading the photo…' : 'Add a piece', kind: DmButtonKind.gold, icon: Icons.photo_camera_outlined,
              onPressed: _adding ? null : () => _add(ImageSource.camera)),
        ),
        const SizedBox(width: 8),
        IconButton(
          tooltip: 'From the gallery',
          onPressed: _adding ? null : () => _add(ImageSource.gallery),
          icon: const Icon(Icons.image_outlined, color: Colors.white),
        ),
      ]),
      children: [
        Wrap(spacing: 6, runSpacing: 6, children: [
          for (final c in const [null, 'top', 'bottom', 'outerwear', 'dress', 'shoes', 'accessory'])
            DmChoiceChip(label: c == null ? 'All' : cap(c), selected: _category == c, onTap: () => setState(() => _category = c)),
        ]),
        const SizedBox(height: 12),
        DmLoad(
          key: ValueKey('items-$_run-$_category'),
          load: () => _api.post('/m01/items', {'user_id': DemoUsers.wardrobe, if (_category != null) 'category': _category}),
          builder: (d, _) {
            final items = jsonList(d['items']);
            return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Row(children: [
                Expanded(child: Text('${items.length} pieces', style: DmText.cardTitle)),
                DmSource(mocked: d['mocked'] == true, label: 'M1'),
              ]),
              const SizedBox(height: 10),
              if (items.isEmpty)
                const DmCard(child: DmEmptyState(title: 'Empty', message: 'Add a photo of a piece you own.'))
              else
                Wrap(spacing: 10, runSpacing: 14, children: [
                  for (final it in items)
                    InkWell(
                      onTap: () => _details(context, it),
                      child: DmPieceTile(
                        name: '${it['subcategory'] ?? it['category']}',
                        imageUrl: _api.media((it['image_cutout'] ?? it['image_raw']) as String?),
                        caption: [
                          if (it['colors'] is List && (it['colors'] as List).isNotEmpty) (it['colors'] as List).first['name'],
                          it['material'],
                        ].whereType<String>().join(' · '),
                        width: 104,
                      ),
                    ),
                ]),
            ]);
          },
        ),
        const SizedBox(height: 20),
        const DmSectionHeader(eyebrow: 'M5', title: 'My style profile'),
        const SizedBox(height: 8),
        DmLoad(
          load: () => _api.call('/m05/profile', userId: DemoUsers.wardrobe),
          builder: (d, _) => DmCard(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                const Expanded(child: Text('Profile', style: DmText.cardTitle)),
                DmSource(mocked: d['_mocked'] == true, label: 'M5'),
              ]),
              const SizedBox(height: 6),
              Text(
                d.containsKey('todo') ? 'M5 is not built yet (mock). Your style profile will show here.' : _summary(d),
                style: DmText.body,
              ),
            ]),
          ),
        ),
      ],
    );
  }

  static String _label(Map g) {
    final colors = g['colors'];
    final colour = colors is List && colors.isNotEmpty ? '${(colors.first as Map)['name']} ' : '';
    return '$colour${g['subcategory'] ?? g['category'] ?? 'piece'}';
  }

  /// "Same piece?" -> true = keep both, false/null = cancel the new one.
  Future<bool?> _askDuplicate(Json g, List<Json> dups) async {
    final items = (await _api.post('/m01/items', {'user_id': DemoUsers.wardrobe}))['items'];
    final byId = {for (final it in jsonList(items)) it['item_id']: it};
    if (!mounted) return false;
    return showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        title: const Text('You may already have it'),
        content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('This ${_label(g)} looks like:', style: DmText.body),
          const SizedBox(height: 12),
          Wrap(spacing: 10, runSpacing: 10, children: [
            for (final d in dups.take(3))
              DmPieceTile(
                name: byId[d['item_id']] == null ? '${d['item_id']}' : _label(byId[d['item_id']]!),
                imageUrl: _api.media((byId[d['item_id']]?['image_cutout'] ?? byId[d['item_id']]?['image_raw']) as String?),
                caption: '${pct(d['similarity'])} same',
                width: 96,
              ),
          ]),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('It is another piece, keep it')),
          FilledButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Same piece, don\'t add')),
        ],
      ),
    );
  }

  Future<void> _delete(BuildContext sheet, Json it) async {
    final ok = await showDialog<bool>(
      context: sheet,
      builder: (ctx) => AlertDialog(
        title: const Text('Remove this piece?'),
        content: Text('${_label(it)} will be removed from your wardrobe.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Remove')),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await _api.delete('/m01/items/${it['item_id']}', query: {'user_id': DemoUsers.wardrobe});
      if (sheet.mounted) Navigator.pop(sheet);
      if (mounted) {
        dmToast(context, 'Removed');
        setState(() => _run++);
      }
    } catch (e) {
      if (mounted) dmToast(context, apiError(e));
    }
  }

  static String _summary(Json d) =>
      d.entries.where((e) => !e.key.startsWith('_')).map((e) => '${e.key}: ${e.value}').join('\n');

  void _details(BuildContext context, Json it) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (sheet) => Padding(
        padding: const EdgeInsets.all(20),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(cap('${it['subcategory'] ?? it['category']}'), style: DmText.title),
          const SizedBox(height: 8),
          for (final k in const ['category', 'pattern', 'material', 'season', 'formality', 'brand', 'size'])
            if (it[k] != null && '${it[k]}' != '[]') Text('$k: ${it[k]}', style: DmText.body),
          const SizedBox(height: 8),
          Wrap(spacing: 6, children: [
            for (final c in jsonList(it['colors']))
              Chip(
                avatar: CircleAvatar(backgroundColor: _hex('${c['hex']}')),
                label: Text('${c['name']} ${pct(c['share'])}'),
              ),
          ]),
          const SizedBox(height: 12),
          FutureBuilder<Json>(
            future: _api.post('/m01/similar', {'user_id': DemoUsers.wardrobe, 'item_id': it['item_id'], 'k': 3, 'threshold': 0.8}),
            builder: (_, snap) {
              final near = jsonList(snap.data?['items'] ?? snap.data?['neighbours'] ?? snap.data?['similar']);
              if (near.isEmpty) return const SizedBox.shrink();
              return Text('Looks like ${near.length} other piece(s) you own (${near.map((n) => pct(n['similarity'])).join(', ')})',
                  style: DmText.body.copyWith(color: DmColors.warning));
            },
          ),
          const SizedBox(height: 16),
          DmButton('Remove from my wardrobe', kind: DmButtonKind.outline, icon: Icons.delete_outline_rounded,
              onPressed: () => _delete(sheet, it)),
        ]),
      ),
    );
  }

  static Color _hex(String h) {
    final v = int.tryParse(h.replaceFirst('#', ''), radix: 16);
    return v == null ? DmColors.sand : Color(0xFF000000 | v);
  }
}
