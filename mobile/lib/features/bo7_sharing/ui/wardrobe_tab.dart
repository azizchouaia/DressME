// Owner: BO7 — "Garde-robe": the user's wardrobe from M1, shown as a real closet (rails with hangers, long
// rail, shelf, shoe rack, walnut doors). Adding and removing a piece goes through M1's API (rule 4).
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../../core/design/dressme_design.dart';
import '../data/bo7_models.dart';
import '../data/bo7_repository.dart';
import '../logic/bo7_providers.dart';
import 'widgets.dart';

class WardrobeTab extends ConsumerStatefulWidget {
  const WardrobeTab({super.key});

  @override
  ConsumerState<WardrobeTab> createState() => _WardrobeTabState();
}

class _WardrobeTabState extends ConsumerState<WardrobeTab> {
  bool _open = false;
  String _filter = 'all';

  bool _keep(Garment g) => _filter == 'all' || (_filter == 'tn' ? g.isTunisian : g.category == _filter);

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(currentUserProvider);
    final ward = ref.watch(wardrobeProvider);
    return RefreshIndicator(
      onRefresh: () async => ref.invalidate(wardrobeProvider),
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
        children: [
          Bo7Hero(
            eyebrow: 'Garde-robe · M1',
            title: 'Ma garde-robe',
            subtitle: '${ward.valueOrNull?.length ?? '…'} pièces de $user, lues depuis le module garde-robe (M1). '
                'Défis et cartes utilisent exactement ces pièces. Touche une pièce pour la voir.',
          ),
          const SizedBox(height: 14),
          AsyncBody<List<Garment>>(
            value: ward,
            onRetry: () => ref.invalidate(wardrobeProvider),
            builder: (items) {
              int n(String k) =>
                  k == 'all' ? items.length : items.where((g) => k == 'tn' ? g.isTunisian : g.category == k).length;
              final filters = ['all', ...categoryOrder.where((c) => n(c) > 0), if (n('tn') > 0) 'tn'];
              return Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  PillChoice<String>(
                    options: filters,
                    selected: _filter,
                    label: (k) => '${k == 'tn' ? 'Créateurs tunisiens' : categoryLabels[k]} · ${n(k)}',
                    onSelected: (k) => setState(() => _filter = k),
                  ),
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      OutlinedButton(
                        onPressed: () => setState(() => _open = !_open),
                        child: Text(_open ? 'Fermer les portes' : 'Ouvrir'),
                      ),
                      const SizedBox(width: 8),
                      FilledButton.icon(
                        onPressed: () => showModalBottomSheet<void>(
                          context: context,
                          isScrollControlled: true,
                          builder: (_) => Theme(data: dressMeTheme(), child: const AddPieceSheet()),
                        ),
                        icon: const Icon(Icons.add, size: 18),
                        label: const Text('Ajouter une pièce'),
                      ),
                    ],
                  ),
                  const SizedBox(height: 18),
                  _Closet(
                    garments: items,
                    keep: _keep,
                    open: _open,
                    onOpen: () => setState(() => _open = true),
                  ),
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}

// ------------------------------------------------------------------------------------------- the closet

class _Closet extends StatelessWidget {
  const _Closet({required this.garments, required this.keep, required this.open, required this.onOpen});

  final List<Garment> garments;
  final bool Function(Garment) keep;
  final bool open;
  final VoidCallback onOpen;

  List<Garment> _of(Set<String> cats) => garments.where((g) => cats.contains(g.category)).toList();

  @override
  Widget build(BuildContext context) {
    final tops = _of({'top', 'outerwear'});
    final bottoms = _of({'bottom'});
    final long = _of({'dress', 'traditional'});
    final shoes = _of({'shoes'});
    final other = _of({'accessory'});
    return Column(
      children: [
        // crown of the closet: walnut with a gold line
        Container(
          height: 20,
          margin: const EdgeInsets.symmetric(horizontal: 2),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(8),
            gradient: const LinearGradient(
                begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF3A2E24), DmColors.ink]),
            border: const Border(bottom: BorderSide(color: DmColors.gold, width: 2)),
            boxShadow: const [BoxShadow(color: Color(0x44211D19), blurRadius: 12, offset: Offset(0, 6))],
          ),
        ),
        ClipRRect(
          borderRadius: const BorderRadius.vertical(bottom: Radius.circular(10)),
          child: Container(
            padding: const EdgeInsets.fromLTRB(10, 12, 10, 12),
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [Color(0xFFF4F1EA), Color(0xFFE9E3D7)]),
            ),
            child: Stack(
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _Compartment(label: 'Hauts & vestes', count: tops.length, child: _Rail(items: tops, keep: keep)),
                    _Compartment(
                        label: 'Pantalons, shorts & jupes',
                        count: bottoms.length,
                        child: _Rail(items: bottoms, keep: keep)),
                    if (long.isNotEmpty)
                      _Compartment(
                          label: 'Robes & jebbas',
                          count: long.length,
                          child: _Rail(items: long, keep: keep, long: true)),
                    if (other.isNotEmpty)
                      _Compartment(
                          label: 'Sacs & accessoires', count: other.length, child: _Shelf(items: other, keep: keep)),
                    _Compartment(
                        label: 'Chaussures',
                        count: shoes.length,
                        suffix: 'paires',
                        child: _Shelf(items: shoes, keep: keep, rack: true)),
                  ],
                ),
                Positioned.fill(child: _Doors(open: open, onTap: onOpen)),
              ],
            ),
          ),
        ),
        Container(
          height: 12,
          margin: const EdgeInsets.symmetric(horizontal: 22),
          decoration: const BoxDecoration(
            borderRadius: BorderRadius.vertical(bottom: Radius.circular(6)),
            gradient: LinearGradient(colors: [Color(0xFFD8CFBD), Color(0xFFC4B9A4)]),
          ),
        ),
      ],
    );
  }
}

class _Compartment extends StatelessWidget {
  const _Compartment({required this.label, required this.count, required this.child, this.suffix});

  final String label;
  final int count;
  final String? suffix;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.fromLTRB(10, 10, 10, 8),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(8),
        gradient: const RadialGradient(
          center: Alignment(0, -1.4),
          radius: 1.6,
          colors: [Color(0xFFFFFDF8), Color(0xFFF3EEE4), Color(0xFFE7DFD1)],
        ),
        border: Border.all(color: const Color(0xFFDDD3C2)),
        boxShadow: const [BoxShadow(color: Color(0x14000000), blurRadius: 10, spreadRadius: -4, offset: Offset(0, 6))],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // brass label
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(4),
              gradient: const LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [Color(0xFFE9D39A), Color(0xFFC9A95B)]),
              boxShadow: const [BoxShadow(color: Color(0x40000000), blurRadius: 2, offset: Offset(0, 1))],
            ),
            child: Text(
              '${label.toUpperCase()}  $count${suffix != null ? ' $suffix' : ''}',
              style: const TextStyle(
                  fontSize: 10, letterSpacing: 1, fontWeight: FontWeight.w700, color: Color(0xFF4B3A24)),
            ),
          ),
          const SizedBox(height: 6),
          child,
        ],
      ),
    );
  }
}

/// A clothes rail: chrome bar, hangers, each garment hanging from its hanger.
class _Rail extends StatelessWidget {
  const _Rail({required this.items, required this.keep, this.long = false});

  final List<Garment> items;
  final bool Function(Garment) keep;
  final bool long;

  @override
  Widget build(BuildContext context) {
    final h = long ? 290.0 : 210.0;
    if (items.isEmpty) {
      return const SizedBox(height: 40, child: Center(child: Text('Rien ici pour l\'instant', style: DmText.caption)));
    }
    return SizedBox(
      height: h,
      child: Stack(
        children: [
          Positioned(
            left: 2,
            right: 2,
            top: 12,
            child: Container(
              height: 8,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(5),
                gradient: const LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [Color(0xFFFAFAFA), Color(0xFFB9BEC6), Color(0xFF868C95), Color(0xFFD9DCE1)],
                ),
                boxShadow: const [BoxShadow(color: Color(0x40000000), blurRadius: 4, offset: Offset(0, 3))],
              ),
            ),
          ),
          Positioned.fill(
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              itemCount: items.length,
              itemBuilder: (_, i) => _Hanging(garment: items[i], dim: !keep(items[i]), height: h),
            ),
          ),
        ],
      ),
    );
  }
}

class _Hanging extends StatelessWidget {
  const _Hanging({required this.garment, required this.dim, required this.height});

  final Garment garment;
  final bool dim;
  final double height;

  @override
  Widget build(BuildContext context) {
    return Opacity(
      opacity: dim ? 0.18 : 1,
      child: InkWell(
        onTap: () => showPieceSheet(context, garment),
        child: SizedBox(
          width: 104,
          child: Stack(
            clipBehavior: Clip.none,
            children: [
              const Positioned(
                  left: 22,
                  top: 0,
                  child: SizedBox(width: 60, height: 40, child: CustomPaint(painter: _HangerPainter()))),
              Positioned(left: 4, right: 4, top: 30, bottom: 2, child: GarmentImage(garment, fit: BoxFit.contain)),
              if (garment.isTunisian)
                Positioned(
                  top: 34,
                  right: 2,
                  child: Transform.rotate(
                    angle: 0.14,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      constraints: const BoxConstraints(maxWidth: 80),
                      decoration: BoxDecoration(color: const Color(0xFFB0573E), borderRadius: BorderRadius.circular(3)),
                      child: Text(garment.localTag!,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontSize: 9, color: Colors.white, fontWeight: FontWeight.w600)),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Metal hanger: hook on the rail and two shoulders.
class _HangerPainter extends CustomPainter {
  const _HangerPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width, h = size.height;
    final p = Paint()
      ..color = const Color(0xFF8F949C)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.4
      ..strokeCap = StrokeCap.round;
    final hook = Path()
      ..moveTo(w / 2, h * 0.55)
      ..lineTo(w / 2, h * 0.3)
      ..arcToPoint(Offset(w / 2 + 6, h * 0.12), radius: const Radius.circular(6), clockwise: true)
      ..arcToPoint(Offset(w / 2 - 2, h * 0.08), radius: const Radius.circular(6), clockwise: false);
    canvas.drawPath(hook, p);
    final shoulders = Path()
      ..moveTo(2, h * 0.95)
      ..lineTo(w / 2, h * 0.55)
      ..lineTo(w - 2, h * 0.95)
      ..close();
    canvas.drawPath(shoulders, p..color = const Color(0xFFA1A6AE));
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

/// A wooden shelf (accessories) or a shoe rack.
class _Shelf extends StatelessWidget {
  const _Shelf({required this.items, required this.keep, this.rack = false});

  final List<Garment> items;
  final bool Function(Garment) keep;
  final bool rack;

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) {
      return const SizedBox(height: 40, child: Center(child: Text('Rien ici pour l\'instant', style: DmText.caption)));
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SizedBox(
          height: rack ? 74 : 96,
          child: ListView(
            scrollDirection: Axis.horizontal,
            children: [
              for (final g in items)
                Opacity(
                  opacity: keep(g) ? 1 : 0.18,
                  child: InkWell(
                    onTap: () => showPieceSheet(context, g),
                    child: SizedBox(
                        width: rack ? 92 : 96,
                        child: Padding(padding: const EdgeInsets.all(4), child: GarmentImage(g))),
                  ),
                ),
            ],
          ),
        ),
        Container(
          height: 8,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(3),
            gradient: const LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Color(0xFFD8CDB6), Color(0xFFA8997B)]),
            boxShadow: const [BoxShadow(color: Color(0x4D000000), blurRadius: 6, offset: Offset(0, 5))],
          ),
        ),
      ],
    );
  }
}

/// Two walnut doors with gold mouldings and brass knobs; they slide away when the closet opens.
class _Doors extends StatelessWidget {
  const _Doors({required this.open, required this.onTap});

  final bool open;
  final VoidCallback onTap;

  Widget _door(bool left) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 2),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(10),
        gradient: const LinearGradient(colors: [Color(0xFF2B241E), Color(0xFF3D332A), Color(0xFF2B241E)]),
        border: Border.all(color: DmColors.gold, width: 1),
        boxShadow: const [BoxShadow(color: Color(0x40000000), blurRadius: 18, offset: Offset(0, 8))],
      ),
      child: Stack(
        children: [
          Positioned.fill(
            child: Container(
              margin: const EdgeInsets.fromLTRB(18, 24, 18, 24),
              decoration: BoxDecoration(
                borderRadius: const BorderRadius.vertical(top: Radius.circular(400), bottom: Radius.circular(6)),
                border: Border.all(color: DmColors.gold.withValues(alpha: 0.55), width: 1.4),
              ),
            ),
          ),
          Align(
            alignment: left ? const Alignment(0.88, 0) : const Alignment(-0.88, 0),
            child: Container(
              width: 14,
              height: 14,
              decoration: const BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(
                    center: Alignment(-0.3, -0.4), colors: [Color(0xFFFFE9A8), Color(0xFFB8862B), Color(0xFF7A5414)]),
                boxShadow: [BoxShadow(color: Color(0x66000000), blurRadius: 3, offset: Offset(0, 2))],
              ),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      ignoring: open,
      child: GestureDetector(
        onTap: onTap,
        child: Row(
          children: [
            Expanded(
              child: AnimatedSlide(
                duration: const Duration(milliseconds: 900),
                curve: Curves.easeInOutCubic,
                offset: open ? const Offset(-1.05, 0) : Offset.zero,
                child: AnimatedOpacity(
                    duration: const Duration(milliseconds: 900), opacity: open ? 0 : 1, child: _door(true)),
              ),
            ),
            Expanded(
              child: AnimatedSlide(
                duration: const Duration(milliseconds: 900),
                curve: Curves.easeInOutCubic,
                offset: open ? const Offset(1.05, 0) : Offset.zero,
                child: AnimatedOpacity(
                    duration: const Duration(milliseconds: 900), opacity: open ? 0 : 1, child: _door(false)),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ------------------------------------------------------------------------------------------- one piece

void showPieceSheet(BuildContext context, Garment g) {
  showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    builder: (_) => Theme(data: dressMeTheme(), child: _PieceSheet(garment: g)),
  );
}

class _PieceSheet extends ConsumerWidget {
  const _PieceSheet({required this.garment});

  final Garment garment;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final g = garment;
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          DmSectionHeader(eyebrow: categoryLabels[g.category] ?? g.category, title: g.name),
          const SizedBox(height: 12),
          Container(
            height: 260,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(color: DmColors.canvas, borderRadius: BorderRadius.circular(DmRadius.panel)),
            child: GarmentImage(g),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              if (g.color != null)
                Chip(
                  avatar: CircleAvatar(backgroundColor: hexColor(g.colorHex), radius: 7),
                  label: Text(g.color!),
                ),
              if (g.isTunisian) DmPill('Créateur tunisien · ${g.localTag}'),
              DmPill('Source : ${g.source ?? 'M1'}'),
            ],
          ),
          const SizedBox(height: 16),
          OutlinedButton.icon(
            onPressed: () async {
              try {
                await ref.read(bo7RepositoryProvider).deleteGarment(ref.read(currentUserProvider), g.id);
                ref.invalidate(wardrobeProvider);
                if (context.mounted) {
                  Navigator.pop(context);
                  showSnack(context, 'Pièce retirée de ta garde-robe');
                }
              } on Bo7Exception catch (e) {
                if (context.mounted) showSnack(context, e.message);
              }
            },
            icon: const Icon(Icons.delete_outline, size: 18),
            label: const Text('Retirer de ma garde-robe'),
          ),
        ],
      ),
    );
  }
}

/// Photo → M1 (classify + update) with the name, category and Tunisian shop typed by the user.
class AddPieceSheet extends ConsumerStatefulWidget {
  const AddPieceSheet({super.key});

  @override
  ConsumerState<AddPieceSheet> createState() => _AddPieceSheetState();
}

class _AddPieceSheetState extends ConsumerState<AddPieceSheet> {
  final _name = TextEditingController();
  String _category = 'top';
  String? _shop;
  String? _image; // data URI
  bool _busy = false;

  Future<void> _pick(ImageSource source) async {
    final f = await ImagePicker().pickImage(source: source, maxWidth: 1400);
    if (f == null) return;
    final bytes = await f.readAsBytes();
    if (mounted) setState(() => _image = 'data:${f.mimeType ?? 'image/jpeg'};base64,${base64Encode(bytes)}');
  }

  Future<void> _save() async {
    final img = _image;
    if (img == null) {
      showSnack(context, 'Choisis d\'abord une photo.');
      return;
    }
    setState(() => _busy = true);
    try {
      await ref.read(bo7RepositoryProvider).addGarment(
            ref.read(currentUserProvider),
            imageDataUri: img,
            category: _category,
            name: _name.text.trim(),
            localTag: _shop,
          );
      ref.invalidate(wardrobeProvider);
      if (mounted) {
        Navigator.pop(context);
        showSnack(context, 'Pièce suspendue dans ta garde-robe');
      }
    } on Bo7Exception catch (e) {
      if (mounted) showSnack(context, e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final shops = ref.watch(shopsProvider).valueOrNull ?? const <Shop>[];
    final img = _image;
    return Padding(
      padding: EdgeInsets.fromLTRB(20, 20, 20, 20 + MediaQuery.of(context).viewInsets.bottom),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const DmSectionHeader(eyebrow: 'Garde-robe · M1', title: 'Ajouter une pièce'),
            const SizedBox(height: 12),
            Container(
              height: 200,
              decoration: BoxDecoration(color: DmColors.canvas, borderRadius: BorderRadius.circular(DmRadius.panel)),
              child: img == null
                  ? const Center(child: Icon(Icons.add_a_photo_outlined, size: 40, color: DmColors.borderStrong))
                  : Image.memory(base64Decode(img.split(',').last), fit: BoxFit.contain),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () => _pick(ImageSource.gallery),
                    icon: const Icon(Icons.photo_library_outlined, size: 18),
                    label: const Text('Galerie'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () => _pick(ImageSource.camera),
                    icon: const Icon(Icons.photo_camera_outlined, size: 18),
                    label: const Text('Appareil photo'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            TextField(
                controller: _name,
                maxLength: 40,
                decoration: const InputDecoration(hintText: 'Nom (ex. jebba blanche)', counterText: '')),
            const SizedBox(height: 8),
            DropdownButtonFormField<String>(
              initialValue: _category,
              items: [for (final c in categoryOrder) DropdownMenuItem(value: c, child: Text(categoryLabels[c] ?? c))],
              onChanged: (v) => setState(() => _category = v ?? 'top'),
            ),
            const SizedBox(height: 8),
            Autocomplete<String>(
              optionsBuilder: (v) => shops
                  .map((s) => s.name)
                  .where((n) => v.text.isNotEmpty && n.toLowerCase().contains(v.text.toLowerCase())),
              onSelected: (v) => _shop = v,
              fieldViewBuilder: (context, ctrl, focus, onSubmit) => TextField(
                controller: ctrl,
                focusNode: focus,
                onChanged: (v) => _shop = v.trim().isEmpty ? null : v.trim(),
                decoration: const InputDecoration(hintText: 'Boutique ou créateur tunisien (facultatif, M7)'),
              ),
            ),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: _busy ? null : _save,
              child: Text(_busy ? 'Analyse par M1…' : 'La suspendre dans ma garde-robe'),
            ),
          ],
        ),
      ),
    );
  }
}
