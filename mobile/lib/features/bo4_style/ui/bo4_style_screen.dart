// Owner: BO4 (Amine) — "Your wardrobe, digitised": the M1 closet, as Amine presents it in his web app
// (backend/modules/m01_wardrobe/ui): three sections (accessories shelves · clothes rails · shoe shelves),
// filters by category and season, add a photo (cutout, classification, colours), duplicate question,
// piece sheet (colours, information, details, analysis, similar pieces), give-away bag.
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../../core/api/dm_api.dart';
import '../../../core/design/dressme_design.dart';
import '../../../core/widgets/dm_widgets.dart';
import '../data/m1_wardrobe.dart';
import 'piece_sheet.dart';

const _bays = [('accessories', 'Accessories'), ('clothes', 'Clothes'), ('shoes', 'Shoes')];

class StyleProfileScreen extends ConsumerStatefulWidget {
  const StyleProfileScreen({super.key});

  @override
  ConsumerState<StyleProfileScreen> createState() => _WardrobeScreenState();
}

class _WardrobeScreenState extends ConsumerState<StyleProfileScreen> {
  late final M1 m1 = M1(ref.read(dmApiProvider), DemoUsers.wardrobe);
  List<Json> items = [];
  Set<String> dupIds = {};
  final newIds = <String>{};
  String? category;
  String? season;
  String bay = 'clothes';
  bool loading = true;
  bool adding = false;
  bool mocked = false;
  String? error;
  int bagCount = 0;
  bool resumed = false;

  @override
  void initState() {
    super.initState();
    _load().then((_) {
      if (!resumed) {
        resumed = true;
        _resumePending();
      }
    });
  }

  Future<void> _load() async {
    setState(() => error = null);
    try {
      final data = await m1.items(category: category, season: season);
      final dups = await m1.duplicateIds();
      int bag = bagCount;
      try {
        bag = jsonList((await m1.items(status: 'donated'))['items']).length;
      } catch (_) {}
      if (!mounted) return;
      setState(() {
        items = jsonList(data['items']);
        mocked = data['mocked'] == true;
        dupIds = dups;
        bagCount = bag;
        loading = false;
      });
    } catch (e) {
      if (mounted) {
        setState(() {
          error = apiError(e);
          loading = false;
        });
      }
    }
  }

  // ---------- add a photo (Amine's addPhoto) ----------
  Future<void> _add(ImageSource source) async {
    final file = await ImagePicker().pickImage(source: source, maxWidth: 1280, maxHeight: 1280, imageQuality: 90);
    if (file == null) return;
    setState(() => adding = true);
    try {
      final bytes = await file.readAsBytes();
      final res = await m1.classify('data:image/jpeg;base64,${base64Encode(bytes)}');
      var g = (res['garment'] as Map).cast<String, dynamic>();
      final dups = jsonList(res['duplicates']);
      if (res['pending'] == true) {
        // M1 held the piece (status pending): nothing is added until the user decides
        final active = await _resolvePending(g, dups);
        if (active == null) return;
        g = active;
      }
      newIds.add('${g['item_id']}');
      if ((category != null && category != g['category']) ||
          (season != null && !(g['season'] as List? ?? const []).contains(season))) {
        category = null;
        season = null;
      }
      bay = shelf(g);
      await _load();
      if (!mounted) return;
      dmToast(context, 'New piece "${pieceTitle(g)}", put in the ${shelf(g)} section.');
      if (res['needs_confirmation'] == true) {
        dmToast(context, 'Confidence ${pct(g['confidence'])}: check the proposed category.');
      }
      // optional right away: size, price, receipt…
      final saved = await Navigator.of(context).push<Json>(
        MaterialPageRoute(fullscreenDialog: true, builder: (_) => PieceForm(m1: m1, item: g, intro: true)),
      );
      if (saved != null) await _load();
    } catch (e) {
      if (mounted) dmToast(context, 'Analysis failed: ${apiError(e)}');
    } finally {
      if (mounted) setState(() => adding = false);
    }
  }

  /// Ask, then confirm (returns the active piece) or cancel (deletes it, returns null).
  Future<Json?> _resolvePending(Json g, List<Json> dups) async {
    final keep = await askDuplicate(context, m1, g, dups);
    if (!keep) {
      await m1.delete('${g['item_id']}');
      if (mounted) dmToast(context, 'Add cancelled: the piece was not added to the wardrobe.');
      return null;
    }
    final active = await m1.confirm('${g['item_id']}');
    dupIds = {...dupIds, '${active['item_id']}', for (final d in dups) '${d['item_id']}'};
    return active;
  }

  /// Pieces left pending (app closed before deciding) are asked again when the wardrobe opens.
  Future<void> _resumePending() async {
    List<Json> held;
    try {
      held = jsonList((await m1.items(status: 'pending'))['items']);
    } catch (_) {
      return;
    }
    for (final it in held) {
      if (!mounted) return;
      var dups = <Json>[];
      try {
        dups = await m1.similar('${it['item_id']}', k: 2, threshold: duplicateThreshold);
      } catch (_) {}
      try {
        final active = await _resolvePending(it, dups);
        if (active != null) {
          newIds.add('${active['item_id']}');
          await _load();
          if (mounted) dmToast(context, '"${pieceTitle(active)}" added to the wardrobe.');
        }
      } catch (e) {
        if (mounted) dmToast(context, 'Decision not saved: ${apiError(e)}');
      }
    }
  }

  void _open(Json it) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (_) => PieceSheet(
        m1: m1,
        item: it,
        isNew: newIds.contains(it['item_id']),
        isDup: dupIds.contains(it['item_id']),
        onChanged: _load,
      ),
    );
  }

  Future<void> _openBag() async {
    List<Json> given;
    try {
      given = jsonList((await m1.items(status: 'donated'))['items']);
    } catch (e) {
      if (mounted) dmToast(context, apiError(e));
      return;
    }
    given.sort((a, b) => '${b['donated_at']}'.compareTo('${a['donated_at']}'));
    if (!mounted) return;
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (_) => DraggableScrollableSheet(
        expand: false,
        initialChildSize: 0.6,
        builder: (_, c) => ListView(controller: c, padding: const EdgeInsets.all(20), children: [
          Text('Bag'.toUpperCase(), style: DmText.eyebrow),
          const Text('To give away', style: DmText.title),
          const SizedBox(height: 6),
          Text(given.isEmpty
              ? 'Your bag is empty. Open a duplicated piece to give it away.'
              : '${given.length} piece(s) ready for a second life.', style: DmText.body),
          const SizedBox(height: 12),
          for (final it in given)
            ListTile(
              leading: Container(
                decoration: BoxDecoration(color: DmColors.sand, borderRadius: BorderRadius.circular(DmRadius.small)),
                child: PieceImage(m1: m1, item: it, size: 52),
              ),
              title: Text(pieceTitle(it)),
              subtitle: Text([
                if (it['donated_at'] != null) 'Put aside on ${'${it['donated_at']}'.split('T').first}',
                if (it['donation_place'] != null) donationPlaces[it['donation_place']] ?? '${it['donation_place']}',
              ].join(' · ')),
            ),
        ]),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final groups = {for (final (b, _) in _bays) b: <Json>[]};
    for (final it in items) {
      groups[shelf(it)]!.add(it);
    }
    final filtered = category != null || season != null;
    return Scaffold(
      backgroundColor: DmColors.page,
      body: ListView(padding: EdgeInsets.zero, children: [
        DmHero(
          eyebrow: 'BO4 · Module M1 · Wardrobe digitiser',
          title: 'Your wardrobe, digitised',
          trailing: Badge(
            isLabelVisible: bagCount > 0,
            label: Text('$bagCount'),
            backgroundColor: DmColors.gold,
            child: IconButton(
              tooltip: 'To give away',
              onPressed: _openBag,
              icon: const Icon(Icons.shopping_bag_outlined, color: Colors.white),
            ),
          ),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('Every piece is cut out, classified and put in the right place.',
                style: DmText.body.copyWith(color: DmColors.goldLight)),
            const SizedBox(height: 12),
            Row(children: [
              Expanded(
                child: DmButton(adding ? 'Analysing: cutout, classification, colours…' : 'Add a piece',
                    kind: DmButtonKind.gold, icon: Icons.photo_camera_outlined, onPressed: adding ? null : () => _add(ImageSource.camera)),
              ),
              IconButton(
                tooltip: 'From the gallery',
                onPressed: adding ? null : () => _add(ImageSource.gallery),
                icon: const Icon(Icons.image_outlined, color: Colors.white),
              ),
            ]),
          ]),
        ),
        Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 760),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 40),
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                // filters: category · season · reset (Amine's toolbar)
                Wrap(spacing: 10, runSpacing: 8, crossAxisAlignment: WrapCrossAlignment.center, children: [
                  _Drop(label: 'Category', value: category, options: categories, onChanged: (v) {
                    setState(() => category = v);
                    _load();
                  }),
                  _Drop(label: 'Season', value: season, options: seasons, onChanged: (v) {
                    setState(() => season = v);
                    _load();
                  }),
                  if (filtered)
                    TextButton(
                      onPressed: () {
                        setState(() {
                          category = null;
                          season = null;
                        });
                        _load();
                      },
                      child: const Text('Reset'),
                    ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: mocked ? DmColors.warningBg : DmColors.successBg,
                      borderRadius: BorderRadius.circular(DmRadius.pill),
                    ),
                    child: Text(mocked ? 'Demo · mock data' : 'Live · FashionCLIP',
                        style: DmText.caption.copyWith(fontWeight: FontWeight.w700)),
                  ),
                ]),
                const SizedBox(height: 12),
                Text('${items.length} piece(s)${filtered ? ' (filtered)' : ''}', style: DmText.cardTitle),
                const SizedBox(height: 10),
                // the three sections of the closet
                Row(children: [
                  for (final (b, label) in _bays)
                    Padding(
                      padding: const EdgeInsets.only(right: 6),
                      child: DmChoiceChip(label: '$label (${groups[b]!.length})', selected: bay == b, onTap: () => setState(() => bay = b)),
                    ),
                ]),
                const SizedBox(height: 12),
                if (loading)
                  const Padding(padding: EdgeInsets.all(40), child: Center(child: CircularProgressIndicator()))
                else if (error != null)
                  DmCard(child: DmEmptyState(icon: Icons.wifi_off_rounded, title: 'Something went wrong', message: error!,
                      action: DmButton('Try again', onPressed: _load)))
                else
                  _Closet(
                    bay: bay,
                    items: groups[bay]!,
                    m1: m1,
                    newIds: newIds,
                    dupIds: dupIds,
                    onTap: _open,
                  ),
              ]),
            ),
          ),
        ),
      ]),
    );
  }
}

class _Drop extends StatelessWidget {
  const _Drop({required this.label, required this.value, required this.options, required this.onChanged});

  final String label;
  final String? value;
  final Map<String, String> options;
  final ValueChanged<String?> onChanged;

  @override
  Widget build(BuildContext context) => SizedBox(
        width: 190,
        child: DropdownButtonFormField<String?>(
          key: ValueKey('$label-$value'),
          initialValue: value,
          isExpanded: true,
          decoration: InputDecoration(labelText: label, isDense: true),
          items: [
            const DropdownMenuItem<String?>(value: null, child: Text('All')),
            for (final e in options.entries) DropdownMenuItem<String?>(value: e.key, child: Text(e.value)),
          ],
          onChanged: onChanged,
        ),
      );
}

/// One section of the closet: hanging rails for clothes, shelves (2 per shelf) for accessories and shoes.
class _Closet extends StatelessWidget {
  const _Closet({required this.bay, required this.items, required this.m1, required this.newIds, required this.dupIds, required this.onTap});

  final String bay;
  final List<Json> items;
  final M1 m1;
  final Set<String> newIds;
  final Set<String> dupIds;
  final void Function(Json) onTap;

  Widget _piece(Json it, {required bool hanging}) {
    final id = '${it['item_id']}';
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 6),
      child: InkWell(
        onTap: () => onTap(it),
        borderRadius: BorderRadius.circular(DmRadius.card),
        child: SizedBox(
          width: 112,
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            if (hanging) const Icon(Icons.checkroom, size: 30, color: DmColors.bar),
            Stack(children: [
              Container(
                decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(DmRadius.card),
                    boxShadow: const [BoxShadow(color: Color(0x14000000), blurRadius: 6, offset: Offset(0, 2))]),
                padding: const EdgeInsets.all(6),
                child: PieceImage(m1: m1, item: it, size: 96),
              ),
              if (newIds.contains(id))
                const Positioned(top: 4, left: 4, child: newBadge)
              else if (dupIds.contains(id))
                const Positioned(top: 4, left: 4, child: dupBadge),
            ]),
            const SizedBox(height: 4),
            Text(pieceTitle(it), style: DmText.itemName, maxLines: 1, overflow: TextOverflow.ellipsis),
          ]),
        ),
      ),
    );
  }

  Widget _rail(String name, List<Json> list) => Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Text(name.toUpperCase(), style: DmText.eyebrow),
        Container(height: 4, margin: const EdgeInsets.symmetric(vertical: 6),
            decoration: BoxDecoration(color: DmColors.bronze, borderRadius: BorderRadius.circular(2))),
        SizedBox(
          height: 180,
          child: list.isEmpty
              ? const Center(child: Text('Nothing on this rail', style: DmText.caption))
              : ListView(scrollDirection: Axis.horizontal, children: [for (final it in list) _piece(it, hanging: true)]),
        ),
      ]);

  @override
  Widget build(BuildContext context) {
    Widget body;
    if (bay == 'clothes') {
      final upper = items.where((it) => upperRail.contains(it['category'])).toList();
      final lower = items.where((it) => !upperRail.contains(it['category'])).toList();
      body = items.isEmpty
          ? const Padding(padding: EdgeInsets.all(30), child: Center(child: Text('No clothes on the rails', style: DmText.body)))
          : Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              _rail('Upper rail · tops & jackets', upper),
              const SizedBox(height: 10),
              _rail('Lower rail · bottoms, dresses, traditional', lower),
            ]);
    } else {
      final shelves = <List<Json>>[
        for (var i = 0; i < items.length; i += 2) items.sublist(i, i + 2 > items.length ? items.length : i + 2),
      ];
      while (shelves.length < 3) {
        shelves.add(const []);
      }
      body = items.isEmpty
          ? const Padding(padding: EdgeInsets.all(30), child: Center(child: Text('No piece on these shelves', style: DmText.body)))
          : Column(children: [
              for (final row in shelves)
                Container(
                  constraints: const BoxConstraints(minHeight: 150),
                  margin: const EdgeInsets.only(bottom: 8),
                  decoration: const BoxDecoration(border: Border(bottom: BorderSide(color: DmColors.bronze, width: 4))),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [for (final it in row) _piece(it, hanging: false)],
                  ),
                ),
            ]);
    }
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: DmColors.sandDark,
        borderRadius: BorderRadius.circular(DmRadius.panel),
        border: Border.all(color: DmColors.borderStrong, width: 2),
      ),
      child: body,
    );
  }
}
