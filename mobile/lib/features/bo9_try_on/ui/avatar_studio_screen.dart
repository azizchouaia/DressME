// Owner: BO9 (Nadhir) — "My 3D avatar": Nadhir's SMPL-X avatar studio (avatar_studio/), as he built it:
// Build slider (thin -> heavy), body details, Female / Male / Auto with photos. The viewer is his Three.js
// page, served by the API at /viewer (bodies from /presets).
// + DressMe: the user's real wardrobe (M1, BO4) in a tray; tapping a piece puts it on the avatar
// (its colour painted on the body region: top / sleeves, bottom / legs, dress, shoes).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/dm_api.dart';
import '../../../core/auth/auth.dart';
import '../../../core/design/dressme_design.dart';
import '../../bo4_style/data/m1_wardrobe.dart';
import '../../bo7_sharing/ui/share_look.dart';
import 'studio/avatar_frame.dart';

/// Which slot of the body a wardrobe piece takes.
String? _slotOf(Json it) => switch ('${it['category']}') {
      'top' => 'top',
      'outerwear' => 'outer',
      'bottom' => 'bottom',
      'dress' || 'traditional' => 'dress',
      'shoes' => 'shoes',
      _ => null, // accessories are not drawn on the body
    };

/// Short sleeves / short legs from the subcategory.
bool _long(Json it) {
  final s = '${it['subcategory'] ?? ''}'.toLowerCase();
  return !(s.contains('t-shirt') || s.contains('tank') || s.contains('polo') || s.contains('shorts') ||
      s.contains('skirt') || s.contains('summer dress'));
}

const _palette = {
  'black': '#1C1B1A', 'charcoal': '#3B3B3B', 'grey': '#8E8E8E', 'white': '#F7F7F5', 'cream': '#EFE6D2',
  'beige': '#D8C3A5', 'khaki': '#B5A27A', 'camel': '#C19A6B', 'tan': '#A57C52', 'brown': '#6F4E37',
  'navy': '#1F2A44', 'blue': '#2F5DA8', 'denim': '#4A6A8F', 'teal': '#2A7F7F', 'green': '#3E7D4F',
  'olive': '#6B6B3A', 'mint': '#A8D5BA', 'yellow': '#E8C547', 'mustard': '#C9A227', 'orange': '#E07B39',
  'red': '#B3261E', 'burgundy': '#6D1A2B', 'pink': '#E8A0B4', 'purple': '#6A4C93', 'lavender': '#B8A9D9',
  'gold': '#C4A35A', 'silver': '#BFC1C2',
}; // M1 colour names (m01_wardrobe/config.yaml)

/// A piece from Smart Buy ("blazer|navy") as a wardrobe-like item.
Json? _virtualPiece(String? spec) {
  if (spec == null || !spec.contains('|')) return null;
  final parts = spec.split('|');
  final sub = parts[0];
  final colour = parts[1];
  final s = sub.toLowerCase();
  final cat = RegExp('sneaker|loafer|boot|sandal|heel|shoe').hasMatch(s)
      ? 'shoes'
      : RegExp('jean|chino|trouser|pant|short|skirt').hasMatch(s)
          ? 'bottom'
          : RegExp('dress|jebba|kaftan').hasMatch(s)
              ? 'dress'
              : RegExp('jacket|blazer|coat|parka|cardigan').hasMatch(s)
                  ? 'outerwear'
                  : 'top';
  return {
    'item_id': 'try:$spec',
    'category': cat,
    'subcategory': '$sub (new)',
    'colors': [
      {'hex': _palette[colour.toLowerCase()] ?? '#8E8E8E', 'name': colour}
    ],
  };
}

String _hex(Json it) {
  final c = jsonList(it['colors']);
  final h = c.isEmpty ? null : c.first['hex'];
  return h is String && h.startsWith('#') ? h : '#8E8E8E';
}

class AvatarStudioScreen extends ConsumerStatefulWidget {
  const AvatarStudioScreen({super.key, this.wear = const [], this.tryPiece});

  /// item ids to put on at open ("See it on me" from an outfit anywhere in the app)
  final List<String> wear;

  /// a piece the user does not own yet, "subcategory|colour" (Smart Buy, BO5): tried with the wardrobe
  final String? tryPiece;

  @override
  ConsumerState<AvatarStudioScreen> createState() => _AvatarStudioScreenState();
}

class _AvatarStudioScreenState extends ConsumerState<AvatarStudioScreen> {
  String? sex;
  List<Json>? pieces;
  String? error;
  final worn = <String, Json>{}; // slot -> piece

  DmApi get api => ref.read(dmApiProvider);

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final r = await api.post('/m01/items', {'user_id': DemoUsers.wardrobe});
      final res = r['result'] is Map ? (r['result'] as Map).cast<String, dynamic>() : r;
      setState(() => pieces = jsonList(res['items']).where((it) => _slotOf(it) != null).toList());
      final extra = _virtualPiece(widget.tryPiece);
      if (extra != null) _toggle(extra);
      for (final id in widget.wear) {
        final it = pieces!.where((p) => p['item_id'] == id).firstOrNull;
        if (it != null && worn[_slotOf(it)]?['item_id'] != id) _toggle(it);
      }
    } catch (e) {
      setState(() => error = apiError(e));
    }
  }

  void _toggle(Json it) {
    final slot = _slotOf(it)!;
    setState(() {
      if (worn[slot]?['item_id'] == it['item_id']) {
        worn.remove(slot);
      } else {
        worn[slot] = it;
        if (slot == 'dress') {
          worn.remove('top');
          worn.remove('bottom');
        } else if (slot == 'top' || slot == 'bottom') {
          worn.remove('dress');
        }
      }
    });
  }

  Map<String, dynamic> get _outfit => {
        for (final e in worn.entries) e.key: {'color': _hex(e.value), 'long': _long(e.value), 'name': pieceTitle(e.value)},
      };

  Widget _tray() {
    final list = pieces;
    Widget body;
    if (error != null) {
      body = Center(child: Text(error!, style: DmText.caption));
    } else if (list == null) {
      body = const Center(child: CircularProgressIndicator());
    } else if (list.isEmpty) {
      body = const Center(child: Text('No clothes in your wardrobe yet: add pieces in Wardrobe.', style: DmText.caption));
    } else {
      body = ListView(scrollDirection: Axis.horizontal, padding: const EdgeInsets.symmetric(horizontal: 12), children: [
        for (final it in list) _pieceTile(it),
      ]);
    }
    return Container(
      height: 150,
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(top: BorderSide(color: DmColors.border)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 10, 12, 4),
          child: Row(children: [
            const Text('MY WARDROBE · TAP TO WEAR', style: DmText.eyebrow),
            const Spacer(),
            if (worn.isNotEmpty)
              TextButton.icon(
                onPressed: () => setState(worn.clear),
                icon: const Icon(Icons.layers_clear_outlined, size: 16),
                label: const Text('Undress'),
              ),
          ]),
        ),
        Expanded(child: body),
      ]),
    );
  }

  Widget _pieceTile(Json it) {
    final on = worn[_slotOf(it)]?['item_id'] == it['item_id'];
    final src = pieceImage(it);
    return GestureDetector(
      onTap: () => _toggle(it),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        width: 86,
        margin: const EdgeInsets.only(right: 8, bottom: 10),
        padding: const EdgeInsets.all(6),
        decoration: BoxDecoration(
          color: on ? DmColors.sandDark : DmColors.page,
          borderRadius: BorderRadius.circular(DmRadius.card),
          border: Border.all(color: on ? DmColors.gold : DmColors.border, width: on ? 2 : 1),
        ),
        child: Column(children: [
          Expanded(
            child: Stack(children: [
              Positioned.fill(
                child: src == null
                    ? const Icon(Icons.checkroom, color: DmColors.bronze)
                    : Image.network(api.media(src), fit: BoxFit.contain,
                        errorBuilder: (_, __, ___) => const Icon(Icons.checkroom, color: DmColors.bronze)),
              ),
              if (on)
                const Positioned(right: 0, top: 0, child: Icon(Icons.check_circle_rounded, size: 18, color: DmColors.gold)),
            ]),
          ),
          const SizedBox(height: 4),
          Row(children: [
            Container(
              width: 10,
              height: 10,
              decoration: BoxDecoration(
                color: Color(int.parse('FF${_hex(it).substring(1)}', radix: 16)),
                shape: BoxShape.circle,
                border: Border.all(color: DmColors.border),
              ),
            ),
            const SizedBox(width: 4),
            Expanded(child: Text(pieceTitle(it), style: DmText.caption, maxLines: 1, overflow: TextOverflow.ellipsis)),
          ]),
        ]),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final gender = ref.watch(authProvider).user?.gender;
    final s = sex ?? (gender == 'male' ? 'male' : 'female');
    final url = '${apiBaseUrl()}/viewer/index.html?mesh=/presets/${s}_average.glb&v=50';
    return Scaffold(
      backgroundColor: const Color(0xFFF6F4F0), // Nadhir's studio background
      body: Column(children: [
        Container(
          width: double.infinity,
          color: DmColors.inkDeep,
          padding: const EdgeInsets.fromLTRB(20, 16, 12, 14),
          child: SafeArea(
            bottom: false,
            child: Row(children: [
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  const Text('BO9 · AVATAR STUDIO',
                      style: TextStyle(color: DmColors.gold, fontSize: 11, fontWeight: FontWeight.w700, letterSpacing: 2)),
                  const SizedBox(height: 2),
                  const Text('My 3D avatar', style: TextStyle(color: Colors.white, fontFamily: DmFonts.serif, fontSize: 26)),
                  Text(
                    worn.isEmpty
                        ? 'Build your body, then tap pieces of your wardrobe to try them on.'
                        : 'Wearing: ${worn.values.map(pieceTitle).join(' · ')}',
                    style: const TextStyle(color: DmColors.goldLight, fontSize: 13),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ]),
              ),
              if (worn.values.any((p) => !'${p['item_id']}'.startsWith('try:')))
                IconButton(
                  tooltip: 'Share this look',
                  onPressed: () => shareLook(context, ref,
                      [for (final p in worn.values) if (!'${p['item_id']}'.startsWith('try:')) '${p['item_id']}'],
                      title: 'My look', kind: 'outfit'),
                  icon: const Icon(Icons.ios_share_rounded, color: Colors.white),
                ),
              const SizedBox(width: 6),
              SegmentedButton<String>(
                style: SegmentedButton.styleFrom(
                  backgroundColor: Colors.white10,
                  foregroundColor: Colors.white,
                  selectedBackgroundColor: DmColors.gold,
                  selectedForegroundColor: DmColors.inkDeep,
                ),
                showSelectedIcon: false,
                segments: const [
                  ButtonSegment(value: 'female', label: Text('Female')),
                  ButtonSegment(value: 'male', label: Text('Male')),
                ],
                selected: {s},
                onSelectionChanged: (v) => setState(() => sex = v.first),
              ),
            ]),
          ),
        ),
        Expanded(child: AvatarFrame(url: url, outfit: _outfit)),
        _tray(),
      ]),
    );
  }
}
