// Owner: BO4 (Amine) — a piece's sheet, its details form, the duplicate question and the "give away" dialog.
// Same content and flow as Amine's web app (m01_wardrobe/ui/app.js): sheetHTML, formHTML, askDuplicate, askDonation.
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/api/dm_api.dart';
import '../../../core/design/dressme_design.dart';
import '../../../core/widgets/dm_widgets.dart';
import '../data/m1_wardrobe.dart';

/// Picture of a piece (cutout / photo / placeholder icon).
class PieceImage extends StatelessWidget {
  const PieceImage({super.key, required this.m1, required this.item, this.size = 96, this.fit = BoxFit.contain});

  final M1 m1;
  final Json item;
  final double size;
  final BoxFit fit;

  @override
  Widget build(BuildContext context) {
    final src = pieceImage(item);
    return SizedBox(
      width: size,
      height: size,
      child: src == null
          ? const Icon(Icons.checkroom, color: DmColors.bronze)
          : Image.network(m1.api.media(src), fit: fit,
              errorBuilder: (_, __, ___) => const Icon(Icons.checkroom, color: DmColors.bronze)),
    );
  }
}

class Badge2 extends StatelessWidget {
  const Badge2(this.label, {super.key, this.color = DmColors.bronze, this.bg = DmColors.sandDark});

  final String label;
  final Color color;
  final Color bg;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(DmRadius.pill)),
        child: Text(label, style: DmText.caption.copyWith(color: color, fontWeight: FontWeight.w700)),
      );
}

const newBadge = Badge2('New', color: DmColors.successDark, bg: DmColors.successBg);
const dupBadge = Badge2('Duplicate?', color: DmColors.warning, bg: DmColors.warningBg);

Color hexColor(Object? h) {
  final v = int.tryParse('$h'.replaceFirst('#', ''), radix: 16);
  return v == null ? DmColors.sand : Color(0xFF000000 | v);
}

// ------------------------------------------------------------------ the piece sheet
class PieceSheet extends StatefulWidget {
  const PieceSheet({super.key, required this.m1, required this.item, required this.isNew, required this.isDup, required this.onChanged});

  final M1 m1;
  final Json item;
  final bool isNew;
  final bool isDup;
  final VoidCallback onChanged; // something was saved / removed / given: reload the closet

  @override
  State<PieceSheet> createState() => _PieceSheetState();
}

class _PieceSheetState extends State<PieceSheet> {
  late Json item = widget.item;
  late bool dup = widget.isDup;
  List<(Json, Json?)>? similar; // (neighbour, its item)
  String? similarError;

  @override
  void initState() {
    super.initState();
    _loadSimilar();
  }

  Future<void> _loadSimilar() async {
    try {
      final near = await widget.m1.similar('${item['item_id']}');
      final resolved = <(Json, Json?)>[];
      for (final n in near) {
        Json? other;
        try {
          other = await widget.m1.item('${n['item_id']}');
        } catch (_) {}
        resolved.add((n, other));
      }
      if (!mounted) return;
      setState(() {
        similar = resolved;
        if (near.any((n) => (n['similarity'] as num? ?? 0) >= duplicateThreshold)) dup = true;
      });
    } catch (e) {
      if (mounted) setState(() => similarError = apiError(e));
    }
  }

  Future<void> _remove() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Remove "${pieceTitle(item)}" from the wardrobe?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Remove')),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await widget.m1.delete('${item['item_id']}');
      widget.onChanged();
      if (mounted) {
        Navigator.pop(context);
        dmToast(context, '${pieceTitle(item)} removed from the wardrobe.');
      }
    } catch (e) {
      if (mounted) dmToast(context, 'Could not remove: ${apiError(e)}');
    }
  }

  Future<void> _give() async {
    final place = await showDialog<(bool, String?)>(context: context, builder: (_) => DonateDialog(m1: widget.m1, item: item));
    if (place == null || !place.$1) return;
    try {
      await widget.m1.donate('${item['item_id']}', place.$2);
      widget.onChanged();
      if (mounted) {
        Navigator.pop(context);
        dmToast(context, '"${pieceTitle(item)}" is in your give-away bag.');
      }
    } catch (e) {
      if (mounted) dmToast(context, 'Could not give it: ${apiError(e)}');
    }
  }

  Future<void> _edit() async {
    final saved = await Navigator.of(context).push<Json>(
      MaterialPageRoute(fullscreenDialog: true, builder: (_) => PieceForm(m1: widget.m1, item: item)),
    );
    if (saved != null && mounted) {
      setState(() => item = saved);
      widget.onChanged();
      dmToast(context, 'Information saved.');
    }
  }

  @override
  Widget build(BuildContext context) {
    final it = item;
    final colors = jsonList(it['colors']);
    final conf = (it['confidence'] as num?)?.toDouble();
    final formality = (it['formality'] as num?)?.toDouble();
    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.9,
      builder: (_, controller) => ListView(controller: controller, padding: const EdgeInsets.fromLTRB(20, 12, 20, 32), children: [
        Center(
          child: Container(
            height: 220,
            width: double.infinity,
            decoration: BoxDecoration(color: DmColors.sand, borderRadius: BorderRadius.circular(DmRadius.panel)),
            child: PieceImage(m1: widget.m1, item: it, size: 200),
          ),
        ),
        const SizedBox(height: 14),
        Text('${categoryOne[it['category']] ?? it['category']} · ${cap(shelf(it))} section'.toUpperCase(), style: DmText.eyebrow),
        Text(pieceTitle(it), style: DmText.display.copyWith(fontSize: 28)),
        const SizedBox(height: 6),
        Wrap(spacing: 6, runSpacing: 6, children: [
          if (widget.isNew) newBadge,
          if (dup) const Badge2('Possible duplicate', color: DmColors.warning, bg: DmColors.warningBg),
          if (conf != null && conf < confidenceThreshold) const Badge2('To confirm', color: DmColors.warning, bg: DmColors.warningBg),
          if (it['local_tag'] != null) const Badge2('Tunisian piece', color: DmColors.eco, bg: DmColors.ecoBg),
        ]),
        _section('Colours', colors.isEmpty
            ? const Text('No colour detected', style: DmText.caption)
            : Wrap(spacing: 8, runSpacing: 8, children: [
                for (final c in colors)
                  Chip(
                    avatar: CircleAvatar(backgroundColor: hexColor(c['hex'])),
                    label: Text('${cap('${c['name']}')} ${pct(c['share'])}'),
                  ),
              ])),
        _info(it),
        _section('Details', _facts([
          ('Season', jsonListStrings(it['season']).map((s) => seasons[s] ?? s).join(', ').ifEmpty('—')),
          ('Pattern', cap('${it['pattern'] ?? '—'}')),
          ('Material', cap('${it['material'] ?? '—'}')),
          ('Worn', '${it['wear_count'] ?? 0} time(s)${it['last_worn'] != null ? ' · last on ${it['last_worn']}' : ''}'),
        ])),
        _section('Analysis', Column(children: [
          if (formality != null) _Meter(label: 'Formality', value: formality, ends: const ('Casual', 'Dressy')),
          if (conf != null) _Meter(label: 'Classifier confidence', value: conf, ok: conf >= confidenceThreshold),
        ])),
        _section('Similar pieces', _similar()),
        const SizedBox(height: 16),
        if (dup) ...[
          DmButton('Give this piece away', kind: DmButtonKind.gold, icon: Icons.volunteer_activism_outlined, onPressed: _give),
          const SizedBox(height: 6),
          const Text('You own a very close piece: this one can make someone else happy.', style: DmText.caption),
          const SizedBox(height: 10),
        ],
        DmButton('Remove from the wardrobe', kind: DmButtonKind.outline, icon: Icons.delete_outline_rounded, onPressed: _remove),
      ]),
    );
  }

  Widget _info(Json it) {
    final bought = it['purchase_date'] ?? it['purchase_year'];
    final rows = <(String, String)>[
      if (it['price_tnd'] != null) ('Price', '${(it['price_tnd'] as num).toStringAsFixed(3)} TND'),
      if (it['size'] != null) ('Size', '${it['size']}${it['size_system'] != null ? ' (${sizeSystems[it['size_system']] ?? it['size_system']})' : ''}'),
      if (it['brand'] != null) ('Brand', '${it['brand']}'),
      if (bought != null || it['store'] != null) ('Bought', [bought, it['store']].where((v) => v != null).join(' · ')),
      if (it['reference'] != null) ('Reference', '${it['reference']}'),
      if (jsonList(it['composition']).isNotEmpty) ('Composition', composition(it['composition'])),
      if (jsonListStrings(it['care']).isNotEmpty) ('Care', jsonListStrings(it['care']).join('\n')),
      if (it['condition'] != null) ('Condition', conditions[it['condition']] ?? '${it['condition']}'),
      if (it['notes'] != null) ('Notes', '${it['notes']}'),
    ];
    return _section(
      'Information',
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        if (rows.isEmpty)
          const Text('Size, price, brand, purchase…: add them by hand or scan the receipt.', style: DmText.body)
        else
          _facts(rows),
        if (it['receipt_image'] != null)
          TextButton(
            onPressed: () => launchUrl(Uri.parse(widget.m1.api.media('${it['receipt_image']}'))),
            child: const Text('See the saved receipt'),
          ),
      ]),
      action: TextButton(onPressed: _edit, child: Text(rows.isEmpty ? 'Add' : 'Edit')),
    );
  }

  Widget _similar() {
    if (similarError != null) return Text('Could not load similar pieces ($similarError).', style: DmText.caption);
    final s = similar;
    if (s == null) return const LinearProgressIndicator();
    final shown = s.where((e) => e.$2 != null).toList();
    if (shown.isEmpty) return const Text('No similar piece above the threshold (75 %).', style: DmText.caption);
    return SizedBox(
      height: 160,
      child: ListView(scrollDirection: Axis.horizontal, children: [
        for (final (n, other) in shown)
          Container(
            width: 110,
            margin: const EdgeInsets.only(right: 10),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Container(
                decoration: BoxDecoration(color: DmColors.sand, borderRadius: BorderRadius.circular(DmRadius.small)),
                child: PieceImage(m1: widget.m1, item: other!, size: 96),
              ),
              Text(pieceTitle(other), style: DmText.itemName, maxLines: 1, overflow: TextOverflow.ellipsis),
              Text('${pct(n['similarity'])} similar', style: DmText.caption),
              if ((n['similarity'] as num? ?? 0) >= duplicateThreshold) dupBadge,
            ]),
          ),
      ]),
    );
  }
}

Widget _section(String title, Widget child, {Widget? action}) => Padding(
      padding: const EdgeInsets.only(top: 18),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [Expanded(child: Text(title, style: DmText.cardTitle)), if (action != null) action]),
        const SizedBox(height: 8),
        child,
      ]),
    );

Widget _facts(List<(String, String)> rows) => Column(children: [
      for (final (k, v) in rows)
        Padding(
          padding: const EdgeInsets.only(bottom: 6),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            SizedBox(width: 110, child: Text(k, style: DmText.caption)),
            Expanded(child: Text(v, style: DmText.body.copyWith(color: DmColors.text))),
          ]),
        ),
    ]);

List<String> jsonListStrings(Object? v) => [for (final e in (v as List? ?? const [])) '$e'];

extension _IfEmpty on String {
  String ifEmpty(String other) => isEmpty ? other : this;
}

class _Meter extends StatelessWidget {
  const _Meter({required this.label, required this.value, this.ends, this.ok = false});

  final String label;
  final double value;
  final (String, String)? ends;
  final bool ok;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Row(children: [Expanded(child: Text(label, style: DmText.body)), Text(pct(value), style: DmText.cardTitle)]),
          const SizedBox(height: 4),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(value: value.clamp(0, 1), minHeight: 8,
                color: ok ? DmColors.success : DmColors.bar, backgroundColor: DmColors.sand),
          ),
          if (ends != null)
            Row(children: [Text(ends!.$1, style: DmText.caption), const Spacer(), Text(ends!.$2, style: DmText.caption)]),
        ]),
      );
}

// ------------------------------------------------------------------ "you may already have it"
/// Returns true = add anyway, false = cancel the new piece (the safe default).
Future<bool> askDuplicate(BuildContext context, M1 m1, Json fresh, List<Json> duplicates) async {
  final existing = <(Json, double)>[];
  for (final d in duplicates.take(2)) {
    try {
      existing.add((await m1.item('${d['item_id']}'), (d['similarity'] as num? ?? 0).toDouble()));
    } catch (_) {}
  }
  if (!context.mounted) return false;
  Widget card(Json it, String label, double? score, {bool isNew = false}) => Container(
        width: 130,
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: isNew ? DmColors.successBg : DmColors.sand,
          borderRadius: BorderRadius.circular(DmRadius.card),
        ),
        child: Column(children: [
          Text(label, style: DmText.caption, textAlign: TextAlign.center),
          PieceImage(m1: m1, item: it, size: 96),
          Text(pieceTitle(it), style: DmText.itemName, maxLines: 1, overflow: TextOverflow.ellipsis),
          if (score != null) Text('${pct(score)} similar', style: DmText.caption),
        ]),
      );
  final r = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: const Text('This piece looks like one in your wardrobe'),
      content: SingleChildScrollView(
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('It has not been added yet. Do you want to add it anyway?', style: DmText.body),
          const SizedBox(height: 12),
          Wrap(spacing: 10, runSpacing: 10, children: [
            card(fresh, 'New photo', null, isNew: true),
            for (final (it, s) in existing) card(it, 'Already in your wardrobe', s),
          ]),
        ]),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel the add')),
        FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Add anyway')),
      ],
    ),
  );
  return r ?? false;
}

// ------------------------------------------------------------------ give away (donation)
class DonateDialog extends StatefulWidget {
  const DonateDialog({super.key, required this.m1, required this.item});

  final M1 m1;
  final Json item;

  @override
  State<DonateDialog> createState() => _DonateDialogState();
}

class _DonateDialogState extends State<DonateDialog> {
  String city = 'Tunis';
  String? place; // null = not decided yet
  Json? ideas;
  String? error;
  int token = 0;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final t = ++token;
    setState(() {
      ideas = null;
      error = null;
    });
    try {
      final r = await widget.m1.donationIdeas('${widget.item['item_id']}', city == 'Other' ? null : city);
      if (mounted && t == token) setState(() => ideas = r);
    } catch (e) {
      if (mounted && t == token) setState(() => error = apiError(e));
    }
  }

  @override
  Widget build(BuildContext context) {
    final r = ideas;
    return AlertDialog(
      title: Text('Give "${pieceTitle(widget.item)}" away?'),
      content: SizedBox(
        width: 460,
        child: SingleChildScrollView(
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('It goes to your give-away bag: it leaves your wardrobe and your outfits.', style: DmText.body),
            const SizedBox(height: 12),
            const Text('Where to give it?', style: DmText.cardTitle),
            DropdownButton<String>(
              value: city,
              isExpanded: true,
              items: [for (final c in cities) DropdownMenuItem(value: c, child: Text(c))],
              onChanged: (v) {
                setState(() => city = v ?? city);
                _load();
              },
            ),
            if (error != null) Text('Suggestions unavailable: $error', style: DmText.caption),
            if (r == null && error == null) const Padding(padding: EdgeInsets.all(8), child: LinearProgressIndicator()),
            if (r != null) ...[
              Text('${r['message'] ?? ''}', style: DmText.body),
              const SizedBox(height: 8),
              for (final s in jsonList(r['suggestions']))
                Card(
                  color: place == s['place'] ? DmColors.sandDark : null,
                  child: InkWell(
                    onTap: () => setState(() => place = '${s['place']}'),
                    child: Padding(
                      padding: const EdgeInsets.all(10),
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text('${s['name']}', style: DmText.cardTitle),
                        Text('${s['reason']}', style: DmText.body),
                        Text('${s['how']}', style: DmText.caption),
                        Wrap(spacing: 8, children: [
                          if (s['url'] != null)
                            TextButton(onPressed: () => launchUrl(Uri.parse('${s['url']}')), child: const Text('Official site ↗')),
                          if (s['phone'] != null) Text('${s['phone']}', style: DmText.caption),
                          if (s['address'] != null) Text('${s['address']}', style: DmText.caption),
                        ]),
                      ]),
                    ),
                  ),
                ),
              Text(r['llm_used'] == true
                  ? 'Chosen and explained by ${r['model']} (local) from a verified list'
                  : 'Verified list (local LLM unavailable: default order)', style: DmText.caption),
            ],
            const SizedBox(height: 12),
            const Text('To whom? (optional)', style: DmText.cardTitle),
            Wrap(spacing: 6, runSpacing: 6, children: [
              for (final e in donationPlaces.entries)
                DmChoiceChip(label: e.value, selected: place == e.key, onTap: () => setState(() => place = e.key)),
              DmChoiceChip(label: "I don't know yet", selected: place == null, onTap: () => setState(() => place = null)),
            ]),
          ]),
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context, (false, null)), child: const Text('Cancel')),
        FilledButton(onPressed: () => Navigator.pop(context, (true, place)), child: const Text('Put it in the bag')),
      ],
    );
  }
}

// ------------------------------------------------------------------ details form (+ receipt / label scan)
class PieceForm extends StatefulWidget {
  const PieceForm({super.key, required this.m1, required this.item, this.intro = false});

  final M1 m1;
  final Json item;
  final bool intro; // right after adding a photo: everything is optional

  @override
  State<PieceForm> createState() => _PieceFormState();
}

class _PieceFormState extends State<PieceForm> {
  late final Json it = widget.item;
  late final Map<String, TextEditingController> f = {
    'price_tnd': TextEditingController(text: (it['price_tnd'] as num?)?.toStringAsFixed(3) ?? ''),
    'store': TextEditingController(text: it['store'] as String? ?? ''),
    'purchase_date': TextEditingController(text: it['purchase_date'] as String? ?? ''),
    'purchase_year': TextEditingController(text: it['purchase_year']?.toString() ?? ''),
    'brand': TextEditingController(text: it['brand'] as String? ?? ''),
    'reference': TextEditingController(text: it['reference'] as String? ?? ''),
    'size': TextEditingController(text: it['size'] as String? ?? ''),
    'composition': TextEditingController(text: composition(it['composition'])),
    'care': TextEditingController(text: jsonListStrings(it['care']).join('\n')),
    'notes': TextEditingController(text: it['notes'] as String? ?? ''),
    'subcategory': TextEditingController(text: it['subcategory'] as String? ?? ''),
    'pattern': TextEditingController(text: it['pattern'] as String? ?? ''),
    'material': TextEditingController(text: it['material'] as String? ?? ''),
  };
  late String? sizeSystem = it['size_system'] as String?;
  late String? condition = it['condition'] as String?;
  late String category = '${it['category'] ?? 'top'}';
  late Set<String> season = jsonListStrings(it['season']).toSet();
  final detected = <String>{};
  String docKind = 'auto';
  String? docImage;
  bool keepDoc = false;
  bool removeDoc = false;
  String? scanStatus;
  List<Json> lines = const [];
  bool saving = false;
  String? error;

  @override
  void dispose() {
    for (final c in f.values) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _scan() async {
    final file = await ImagePicker().pickImage(source: ImageSource.gallery, maxWidth: 1280, imageQuality: 90);
    if (file == null) return;
    setState(() => scanStatus = 'Reading the document…');
    try {
      docImage = 'data:image/jpeg;base64,${base64Encode(await file.readAsBytes())}';
      final doc = await widget.m1.extract(docImage!, docKind, '${it['item_id']}');
      final x = (doc['fields'] as Map? ?? const {}).cast<String, dynamic>();
      var filled = 0;
      void put(String name, Object? v) {
        if (v == null || '$v'.isEmpty || (v is List && v.isEmpty)) return;
        f[name]!.text = '$v';
        detected.add(name);
        filled++;
      }

      if (x['price'] != null && (x['currency'] == null || x['currency'] == 'TND')) put('price_tnd', (x['price'] as num).toStringAsFixed(3));
      put('purchase_date', x['purchase_date']);
      if (x['purchase_date'] != null) put('purchase_year', '${x['purchase_date']}'.substring(0, 4));
      put('store', x['store']);
      put('brand', x['brand']);
      put('reference', x['reference']);
      put('size', x['size']);
      if (x['size_system'] != null) sizeSystem = '${x['size_system']}';
      put('composition', composition(x['composition']));
      put('care', jsonListStrings(x['care']).join('\n'));
      setState(() {
        lines = jsonList(doc['lines']);
        scanStatus = 'Read: $filled field(s) pre-filled${doc['mocked'] == true ? ' (demo)' : ''}. Check them before saving.';
      });
    } catch (e) {
      final msg = apiError(e);
      setState(() => scanStatus = RegExp('503|unavailable', caseSensitive: false).hasMatch(msg)
          ? 'Automatic reading is not available yet (M8). Fill the form by hand: you can still keep the receipt image.'
          : 'Could not read it: $msg');
    }
  }

  Json? _changes() {
    String? str(String n) => f[n]!.text.trim().isEmpty ? null : f[n]!.text.trim();
    num? number(String n) => str(n) == null ? null : num.tryParse(str(n)!.replaceAll(',', '.'));
    final compText = str('composition') ?? '';
    final comp = parseComposition(compText);
    if (compText.isNotEmpty && comp.isEmpty) {
      setState(() => error = 'Composition: write for example "55 % linen, 45 % cotton".');
      return null;
    }
    final values = <String, Object?>{
      'price_tnd': number('price_tnd'), 'store': str('store'), 'purchase_date': str('purchase_date'),
      'purchase_year': number('purchase_year'), 'brand': str('brand'), 'reference': str('reference'),
      'size': str('size'), 'size_system': sizeSystem, 'composition': comp, 'condition': condition, 'notes': str('notes'),
      'care': (str('care') ?? '').split('\n').map((s) => s.trim()).where((s) => s.isNotEmpty).toList(),
      'category': category, 'subcategory': str('subcategory'), 'pattern': str('pattern'), 'material': str('material'),
      'season': [for (final s in seasons.keys) if (season.contains(s)) s],
    };
    Object? before(String k) {
      final v = it[k];
      if (k == 'composition') return [for (final m in jsonList(v)) {'material': m['material'], 'percent': (m['percent'] as num).toDouble()}];
      if (k == 'care' || k == 'season') return jsonListStrings(v);
      return v;
    }

    final changes = <String, dynamic>{};
    for (final e in values.entries) {
      if (jsonEncode(e.value) != jsonEncode(before(e.key))) changes[e.key] = e.value;
    }
    if (keepDoc && docImage != null) changes['receipt_image'] = docImage;
    if (removeDoc) changes['receipt_image'] = null;
    return changes;
  }

  Future<void> _save() async {
    setState(() => error = null);
    final changes = _changes();
    if (changes == null) return;
    if (changes.isEmpty) {
      Navigator.pop(context);
      return;
    }
    setState(() => saving = true);
    try {
      final saved = await widget.m1.update('${it['item_id']}', changes);
      if (mounted) Navigator.pop(context, saved);
    } catch (e) {
      setState(() {
        error = 'Could not save: ${apiError(e)}';
        saving = false;
      });
    }
  }

  Widget _field(String name, String label, {String? hint, TextInputType? type, int lines = 1}) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: TextField(
          controller: f[name],
          keyboardType: type,
          maxLines: lines,
          onChanged: (_) => setState(() => detected.remove(name)),
          decoration: InputDecoration(
            labelText: label,
            hintText: hint,
            suffixIcon: detected.contains(name) ? const Padding(padding: EdgeInsets.all(12), child: Text('detected', style: DmText.caption)) : null,
          ),
        ),
      );

  Widget _group(String title, List<Widget> children) => Padding(
        padding: const EdgeInsets.only(top: 16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text(title.toUpperCase(), style: DmText.eyebrow),
          const SizedBox(height: 8),
          ...children,
        ]),
      );

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.intro ? 'Complete the information' : 'Information of the piece')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        Text(widget.intro ? 'Optional: you can do it later from the piece sheet.'
            : 'Only the changed fields are saved. Empty a field to clear it.', style: DmText.body),
        if (error != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text(error!, style: DmText.body.copyWith(color: DmColors.warning))),
        _group('Scan a receipt or a label', [
          const Text('What it reads pre-fills the form: check it before saving.', style: DmText.caption),
          Row(children: [
            Expanded(
              child: DropdownButton<String>(
                value: docKind,
                isExpanded: true,
                items: [for (final e in docKinds.entries) DropdownMenuItem(value: e.key, child: Text(e.value))],
                onChanged: (v) => setState(() => docKind = v ?? docKind),
              ),
            ),
            const SizedBox(width: 8),
            OutlinedButton.icon(onPressed: _scan, icon: const Icon(Icons.photo_camera_outlined), label: const Text('Pick a photo')),
          ]),
          CheckboxListTile(
            value: keepDoc,
            onChanged: docImage == null ? null : (v) => setState(() => keepDoc = v ?? false),
            title: const Text('Keep the receipt image with the piece'),
            controlAffinity: ListTileControlAffinity.leading,
            contentPadding: EdgeInsets.zero,
          ),
          if (it['receipt_image'] != null)
            CheckboxListTile(
              value: removeDoc,
              onChanged: (v) => setState(() => removeDoc = v ?? false),
              title: const Text('Delete the saved receipt'),
              controlAffinity: ListTileControlAffinity.leading,
              contentPadding: EdgeInsets.zero,
            ),
          if (scanStatus != null) Text(scanStatus!, style: DmText.caption),
          if (lines.length > 1) ...[
            const SizedBox(height: 6),
            const Text('Which receipt line is this piece?', style: DmText.cardTitle),
            for (final l in lines)
              ListTile(
                dense: true,
                title: Text('${l['label']}'),
                trailing: l['price'] == null ? null : Text('${(l['price'] as num).toStringAsFixed(3)} TND'),
                onTap: () => setState(() {
                  if (l['price'] != null) f['price_tnd']!.text = (l['price'] as num).toStringAsFixed(3);
                  detected.add('price_tnd');
                }),
              ),
          ],
        ]),
        _group('Purchase', [
          _field('price_tnd', 'Price (TND)', hint: '89.000', type: const TextInputType.numberWithOptions(decimal: true)),
          _field('store', 'Store', hint: 'Zara · Tunisia Mall'),
          _field('purchase_date', 'Purchase date (YYYY-MM-DD)', hint: '2026-03-14'),
          _field('purchase_year', '… or only the year', hint: '2015', type: TextInputType.number),
        ]),
        _group('Identity', [
          _field('brand', 'Brand'),
          _field('reference', 'Reference'),
          _field('size', 'Size', hint: 'M, 40, W32 L34'),
          DropdownButtonFormField<String?>(
            initialValue: sizeSystem,
            decoration: const InputDecoration(labelText: 'Size system'),
            items: [
              const DropdownMenuItem<String?>(value: null, child: Text('—')),
              for (final e in sizeSystems.entries) DropdownMenuItem<String?>(value: e.key, child: Text(e.value)),
            ],
            onChanged: (v) => setState(() => sizeSystem = v),
          ),
        ]),
        _group('Material and care', [
          _field('composition', 'Composition', hint: '55 % linen, 45 % cotton'),
          DropdownButtonFormField<String?>(
            initialValue: condition,
            decoration: const InputDecoration(labelText: 'Condition'),
            items: [
              const DropdownMenuItem<String?>(value: null, child: Text('—')),
              for (final e in conditions.entries) DropdownMenuItem<String?>(value: e.key, child: Text(e.value)),
            ],
            onChanged: (v) => setState(() => condition = v),
          ),
          const SizedBox(height: 10),
          _field('care', 'Care (one instruction per line)', lines: 3),
          _field('notes', 'Notes', lines: 2),
        ]),
        _group('Correct the analysis', [
          DropdownButtonFormField<String>(
            initialValue: categoryOne.containsKey(category) ? category : 'top',
            decoration: const InputDecoration(labelText: 'Category'),
            items: [for (final e in categoryOne.entries) DropdownMenuItem(value: e.key, child: Text(e.value))],
            onChanged: (v) => setState(() => category = v ?? category),
          ),
          const SizedBox(height: 10),
          _field('subcategory', 'Type'),
          _field('pattern', 'Pattern'),
          _field('material', 'Main material'),
          Wrap(spacing: 6, children: [
            for (final e in seasons.entries)
              FilterChip(
                label: Text(e.value),
                selected: season.contains(e.key),
                onSelected: (v) => setState(() => v ? season.add(e.key) : season.remove(e.key)),
              ),
          ]),
        ]),
        const SizedBox(height: 20),
        Row(children: [
          Expanded(child: DmButton(widget.intro ? 'Later' : 'Cancel', kind: DmButtonKind.outline, onPressed: () => Navigator.pop(context))),
          const SizedBox(width: 10),
          Expanded(child: DmButton(saving ? 'Saving…' : 'Save', kind: DmButtonKind.gold, onPressed: saving ? null : _save)),
        ]),
      ]),
    );
  }
}
