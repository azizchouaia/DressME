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

String _hex(Json it) {
  final c = jsonList(it['colors']);
  final h = c.isEmpty ? null : c.first['hex'];
  return h is String && h.startsWith('#') ? h : '#8E8E8E';
}

class AvatarStudioScreen extends ConsumerStatefulWidget {
  const AvatarStudioScreen({super.key});

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
