// Owner: BO5 (@azizchouaia) — Smart Buy: "should I buy this piece?" -> verdict, why, size, local shops.
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/design/dressme_design.dart';
import '../../../core/widgets/dm_widgets.dart';
import '../data/bo5_smart_buy_repository.dart';
import '../logic/bo5_smart_buy_provider.dart';

String _cap(String s) => s.isEmpty ? s : '${s[0].toUpperCase()}${s.substring(1)}';
const _critical = Color(0xFFA2453A); // SKIP (not in the kit: verdict colour of BO5 only)

({String word, String sub, Color color}) _verdictStyle(String v) => switch (v) {
      'buy' => (word: 'BUY', sub: 'A good buy for your wardrobe', color: DmColors.success),
      'think' => (word: 'THINK', sub: 'Think twice before paying', color: DmColors.warning),
      _ => (word: 'SKIP', sub: 'You already have what you need', color: _critical),
    };

Color _hex(String h) => Color(int.parse('FF${h.replaceFirst('#', '')}', radix: 16));

class SmartBuyScreen extends ConsumerStatefulWidget {
  const SmartBuyScreen({super.key});

  @override
  ConsumerState<SmartBuyScreen> createState() => _SmartBuyScreenState();
}

class _SmartBuyScreenState extends ConsumerState<SmartBuyScreen> {
  final _price = TextEditingController(text: '120');
  final _fitText = TextEditingController();
  String _type = 'blazer';
  String _colour = 'navy';
  String? _brand;
  String _user = 'usr_demo';
  String _lang = 'en';
  Uint8List? _photo;
  PhotoGuess? _guess;
  bool _reading = false;
  String? _photoError;

  @override
  void dispose() {
    _price.dispose();
    _fitText.dispose();
    super.dispose();
  }

  Future<void> _pickPhoto(ImageSource source) async {
    final file = await ImagePicker().pickImage(source: source, maxWidth: 900, imageQuality: 85);
    if (file == null) return;
    final bytes = await file.readAsBytes();
    setState(() {
      _photo = bytes;
      _reading = true;
      _photoError = null;
      _guess = null;
    });
    try {
      final g = await ref.read(smartBuyRepositoryProvider).analyze('data:image/jpeg;base64,${base64Encode(bytes)}');
      setState(() {
        _guess = g;
        _type = g.subcategory;
        _colour = g.colour;
      });
    } catch (_) {
      setState(() => _photoError = 'I could not read the photo. Pick the type and colour yourself.');
    } finally {
      if (mounted) setState(() => _reading = false);
    }
  }

  Future<void> _judge() async {
    final n = ref.read(smartBuyProvider.notifier)
      ..userId = _user
      ..language = _lang;
    await n.judge(
      probe: 'custom:$_type:$_colour',
      priceTnd: double.tryParse(_price.text.replaceAll(',', '.')),
      shopBrand: _brand,
      fitText: _fitText.text,
      aiConfidence: _guess == null ? null : (_guess!.typeConfidence < _guess!.colourConfidence ? _guess!.typeConfidence : _guess!.colourConfidence),
    );
  }

  @override
  Widget build(BuildContext context) {
    final meta = ref.watch(smartBuyMetaProvider);
    final result = ref.watch(smartBuyProvider);
    return Scaffold(
      body: meta.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(
          child: DmEmptyState(
            icon: Icons.wifi_off_rounded,
            title: 'The server is not answering',
            message: 'Start the API (uvicorn api.main:app), then try again.\n${smartBuyApiUrl()}',
            action: DmButton('Try again', onPressed: () => ref.invalidate(smartBuyMetaProvider)),
          ),
        ),
        data: (m) => ListView(
          padding: EdgeInsets.zero,
          children: [
            DmHero(
              eyebrow: 'Smart Buy · before you pay',
              title: 'Should I buy it?',
              trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                IconButton(
                  tooltip: 'Did you wear it?',
                  onPressed: () => _sheet(context, _CheckinSheet(userId: _user)),
                  icon: _CheckinBadge(userId: _user),
                ),
                IconButton(
                  tooltip: 'My wishlist (price watch)',
                  onPressed: () => _sheet(context, _WishlistSheet(userId: _user)),
                  icon: const Icon(Icons.favorite_border_rounded, color: Colors.white),
                ),
                IconButton(
                  tooltip: 'My shopping list',
                  onPressed: () => _sheet(context, _ShoppingListSheet(userId: _user)),
                  icon: const Icon(Icons.checklist_rounded, color: Colors.white),
                ),
              ]),
              child: Row(children: [
                Text('Wardrobe'.toUpperCase(), style: DmText.eyebrow.copyWith(color: const Color(0xFFCDB18D))),
                const SizedBox(width: 10),
                DropdownButton<String>(
                  value: _user,
                  dropdownColor: DmColors.inkDeep,
                  underline: const SizedBox.shrink(),
                  iconEnabledColor: DmColors.gold,
                  style: const TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w600),
                  items: [for (final u in m.users) DropdownMenuItem(value: u.id, child: Text(u.id.replaceFirst('usr_', '')))],
                  onChanged: (v) => setState(() => _user = v ?? _user),
                ),
              ]),
            ),
            Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 620),
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(16, 20, 16, 40),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                    _pieceCard(m),
                    const SizedBox(height: 16),
                    DmButton(
                      result.isLoading ? 'Thinking…' : 'Should I buy it?',
                      kind: DmButtonKind.gold,
                      icon: Icons.auto_awesome,
                      onPressed: result.isLoading ? null : _judge,
                    ),
                    const SizedBox(height: 20),
                    result.when(
                      loading: () => const Padding(padding: EdgeInsets.all(32), child: Center(child: CircularProgressIndicator())),
                      error: (e, _) => DmCard(child: DmEmptyState(icon: Icons.error_outline, title: 'Something went wrong', message: '$e')),
                      data: (r) => r == null
                          ? const DmCard(
                              child: DmEmptyState(
                                icon: Icons.shopping_bag_outlined,
                                title: 'Show me the piece',
                                message: 'Take a photo or pick a piece, add its price, and I tell you if it is worth it with what you already own.',
                              ),
                            )
                          : _ResultView(result: r, userId: _user, lastPrice: double.tryParse(_price.text.replaceAll(',', '.'))),
                    ),
                  ]),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _pieceCard(SmartBuyMeta m) {
    final colours = m.types[_type] ?? const <String>[];
    if (!colours.contains(_colour) && colours.isNotEmpty) _colour = colours.first;
    return DmCard(
      big: true,
      padding: const EdgeInsets.all(20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const DmSectionHeader(eyebrow: 'The piece in the shop', title: 'Photo or pick one'),
        const SizedBox(height: 14),
        Row(children: [
          Expanded(child: DmButton('Photo', icon: Icons.photo_camera_outlined, onPressed: () => _pickPhoto(ImageSource.camera))),
          const SizedBox(width: 8),
          Expanded(child: DmButton('Gallery', kind: DmButtonKind.outline, icon: Icons.image_outlined, onPressed: () => _pickPhoto(ImageSource.gallery))),
        ]),
        if (_photo != null) ...[
          const SizedBox(height: 14),
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(DmRadius.card),
              child: Image.memory(_photo!, width: 92, height: 112, fit: BoxFit.cover),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _reading
                  ? const Padding(padding: EdgeInsets.only(top: 12), child: Text('The AI is looking at the piece…', style: DmText.body))
                  : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text('AI saw — fix it if wrong'.toUpperCase(), style: DmText.eyebrow),
                      const SizedBox(height: 6),
                      if (_guess != null)
                        Wrap(spacing: 6, runSpacing: 6, children: [
                          DmPill('${_cap(_guess!.subcategory)} · ${(_guess!.typeConfidence * 100).round()} %'),
                          DmPill('${_guess!.colour} · ${(_guess!.colourConfidence * 100).round()} %'),
                        ]),
                      if (_photoError != null) Text(_photoError!, style: DmText.body.copyWith(color: DmColors.warning)),
                    ]),
            ),
          ]),
        ],
        const SizedBox(height: 16),
        Row(children: [
          Expanded(
            child: DropdownButtonFormField<String>(
              key: ValueKey('type-$_type'),
              initialValue: _type,
              decoration: const InputDecoration(labelText: 'Type'),
              items: [for (final t in m.types.keys) DropdownMenuItem(value: t, child: Text(_cap(t)))],
              onChanged: (v) => setState(() => _type = v ?? _type),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: DropdownButtonFormField<String>(
              key: ValueKey('colour-$_type-$_colour'),
              initialValue: colours.contains(_colour) ? _colour : null,
              decoration: const InputDecoration(labelText: 'Colour'),
              items: [
                for (final c in colours)
                  DropdownMenuItem(
                    value: c,
                    child: Row(children: [
                      Container(width: 12, height: 12, decoration: BoxDecoration(color: _hex(m.colours[c] ?? '#999999'), shape: BoxShape.circle, border: Border.all(color: DmColors.border))),
                      const SizedBox(width: 8),
                      Text(_cap(c)),
                    ]),
                  ),
              ],
              onChanged: (v) => setState(() => _colour = v ?? _colour),
            ),
          ),
        ]),
        const SizedBox(height: 12),
        Row(children: [
          Expanded(
            child: TextField(
              controller: _price,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: const InputDecoration(labelText: 'Price', suffixText: 'TND'),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: DropdownButtonFormField<String?>(
              initialValue: _brand,
              decoration: const InputDecoration(labelText: 'Shop brand (for size)'),
              items: [
                const DropdownMenuItem<String?>(value: null, child: Text('— no size advice —')),
                for (final b in m.brands) DropdownMenuItem<String?>(value: b, child: Text(b, overflow: TextOverflow.ellipsis)),
              ],
              onChanged: (v) => setState(() => _brand = v),
            ),
          ),
        ]),
        const SizedBox(height: 12),
        TextField(
          controller: _fitText,
          minLines: 1,
          maxLines: 3,
          decoration: const InputDecoration(
            labelText: 'How do your clothes fit? (optional)',
            hintText: 'e.g. I wear M at Medina Atelier, tight on the shoulders',
          ),
        ),
        const SizedBox(height: 12),
        Row(children: [
          Text('Answer in'.toUpperCase(), style: DmText.eyebrow),
          const SizedBox(width: 10),
          for (final (code, label) in const [('en', 'English'), ('fr', 'Français'), ('ar', 'Tounsi')])
            Padding(
              padding: const EdgeInsets.only(right: 6),
              child: DmChoiceChip(label: label, selected: _lang == code, onTap: () => setState(() => _lang = code)),
            ),
        ]),
      ]),
    );
  }

  void _sheet(BuildContext context, Widget sheet) {
    showModalBottomSheet<void>(context: context, isScrollControlled: true, builder: (_) => sheet);
  }
}

class _ResultView extends ConsumerWidget {
  const _ResultView({required this.result, required this.userId, this.lastPrice});

  final SmartBuyResult result;
  final String userId;
  final double? lastPrice; // the price the user typed (watched by the wishlist)

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final r = result;
    final v = _verdictStyle(r.verdict);
    final notifier = ref.read(smartBuyProvider.notifier);
    final repo = ref.read(smartBuyRepositoryProvider);

    Future<void> watchPrice() async {
      final typed = lastPrice; // the price the user typed is what we watch
      if (r.subcategory == null || r.colour == null || typed == null) return;
      try {
        final w = await repo.addToWishlist(userId: userId, subcategory: r.subcategory!, colour: r.colour!, priceTnd: typed, decisionId: r.decisionId);
        ref.invalidate(wishlistProvider(userId));
        if (context.mounted) dmToast(context, 'On your wishlist. I tell you when it is ${w.targetTnd.round()} TND or less');
      } catch (_) {
        if (context.mounted) dmToast(context, 'Could not save it, try again');
      }
    }

    Future<void> runAction(NextAction a) async {
      switch (a.action) {
        case 'watch_price':
          await watchPrice();
        case 'open_shop' when a.args['url'] != null:
          await launchUrl(Uri.parse('${a.args['url']}'), mode: LaunchMode.externalApplication);
        default:
          dmToast(context, 'Coming soon: ${a.tool ?? ''} through the assistant');
      }
    }

    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      // 1. Verdict
      DmCard(
        big: true,
        padding: const EdgeInsets.all(20),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            _ScoreRing(score: r.score, color: v.color),
            const SizedBox(width: 16),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(r.piece.toUpperCase(), style: DmText.eyebrow),
                Text(v.word, style: DmText.display.copyWith(color: v.color, fontSize: 32)),
                Text(v.sub, style: DmText.body),
              ]),
            ),
          ]),
          const SizedBox(height: 14),
          Text(r.explanation, style: DmText.body.copyWith(fontSize: 14, color: DmColors.text)),
          const SizedBox(height: 4),
          Text(r.explanationByAi ? 'Written by the local AI from the facts below' : 'Template text (local AI off)', style: DmText.caption),
          if (r.verdict == 'think' && r.subcategory != null && lastPrice != null) ...[
            const SizedBox(height: 12),
            DmButton('Watch the price for me', kind: DmButtonKind.outline, icon: Icons.notifications_active_outlined, onPressed: watchPrice),
          ],
          if (r.fillsGoal != null || r.newOutfits > 0) ...[
            const SizedBox(height: 12),
            Wrap(spacing: 6, runSpacing: 6, children: [
              if (r.newOutfits > 0) DmPill('${r.newOutfits} new outfits'),
              if (r.fillsGoal != null) DmPill('Goal: ${r.fillsGoal}'),
              if (r.costPerWear != null) DmPill('${r.costPerWear!.toStringAsFixed(2)} TND per wear'),
            ]),
          ],
        ]),
      ),
      // 2. The agent asks one question when it is a close call
      if (r.question != null) ...[
        const SizedBox(height: 14),
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: DmColors.warningBg,
            borderRadius: BorderRadius.circular(DmRadius.card),
            border: Border.all(color: DmColors.gold),
          ),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('Not sure'.toUpperCase(), style: DmText.eyebrow),
            const SizedBox(height: 4),
            Text(r.question!, style: DmText.body.copyWith(color: DmColors.text, fontSize: 13)),
            if (r.questionKey != null) ...[
              const SizedBox(height: 10),
              Row(children: [
                DmButton('Yes, I need it', onPressed: () => notifier.answer(r.questionKey!, true)),
                const SizedBox(width: 8),
                DmButton('No', kind: DmButtonKind.outline, onPressed: () => notifier.answer(r.questionKey!, false)),
              ]),
            ],
          ]),
        ),
      ],
      // 3. Why
      const SizedBox(height: 14),
      DmCard(
        padding: const EdgeInsets.all(18),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          const DmSectionHeader(eyebrow: 'Why', title: 'What pushed the decision'),
          const SizedBox(height: 12),
          for (final e in r.contributions.entries.take(6)) _ContributionBar(label: e.key, value: e.value),
          const SizedBox(height: 4),
          Text('green = toward BUY · red = toward SKIP', style: DmText.caption),
          const SizedBox(height: 14),
          DmReasons(r.reasons.take(5).toList()),
          if (r.whatIf.isNotEmpty) ...[
            const Divider(height: 24),
            Text('What would change the answer'.toUpperCase(), style: DmText.eyebrow),
            const SizedBox(height: 6),
            for (final w in r.whatIf) Text('→ $w', style: DmText.body),
          ],
        ]),
      ),
      // 4. Similar pieces already owned
      if (r.similar.isNotEmpty) ...[
        const SizedBox(height: 14),
        DmCard(
          padding: const EdgeInsets.all(18),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const DmSectionHeader(eyebrow: 'Already in your wardrobe', title: 'Similar pieces'),
            const SizedBox(height: 10),
            Wrap(spacing: 6, runSpacing: 6, children: [
              for (final s in r.similar.take(4)) DmPill('${s.label} · ${(s.similarity * 100).round()} %'),
            ]),
          ]),
        ),
      ],
      // 5. Size
      if (r.size != null) ...[
        const SizedBox(height: 14),
        DmCard(
          padding: const EdgeInsets.all(18),
          child: Row(children: [
            Container(
              width: 56,
              height: 56,
              alignment: Alignment.center,
              decoration: const BoxDecoration(color: DmColors.inkDeep, shape: BoxShape.circle),
              child: Text(r.size!, style: DmText.title.copyWith(color: Colors.white, fontSize: 20)),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('Your size'.toUpperCase(), style: DmText.eyebrow),
                const SizedBox(height: 2),
                Text(r.sizeNote ?? '', style: DmText.body),
              ]),
            ),
          ]),
        ),
      ],
      // 6. Local shops
      if (r.links.isNotEmpty) ...[
        const SizedBox(height: 20),
        DmSectionHeader(eyebrow: r.links.first.isReal ? 'Tunisian shops' : 'Shops (example)', title: 'Buy locally'),
        const SizedBox(height: 10),
        SizedBox(
          height: 222,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: r.links.length,
            separatorBuilder: (_, __) => const SizedBox(width: 10),
            itemBuilder: (_, i) => _ShopTile(link: r.links[i], userId: userId),
          ),
        ),
      ],
      // 6b. Same look, cheaper
      if (r.alternatives.isNotEmpty) ...[
        const SizedBox(height: 20),
        const DmSectionHeader(eyebrow: 'Same look, less money', title: 'Cheaper look-alikes'),
        const SizedBox(height: 10),
        SizedBox(
          height: 222,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: r.alternatives.length,
            separatorBuilder: (_, __) => const SizedBox(width: 10),
            itemBuilder: (_, i) => _ShopTile(link: r.alternatives[i], userId: userId),
          ),
        ),
      ],
      // 7. Memory + next steps + feedback
      if (r.memoryNotes.isNotEmpty) ...[
        const SizedBox(height: 14),
        DmCard(
          padding: const EdgeInsets.all(16),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('Smart Buy remembered'.toUpperCase(), style: DmText.eyebrow),
            const SizedBox(height: 6),
            for (final n in r.memoryNotes) Text('• $n', style: DmText.body),
          ]),
        ),
      ],
      const SizedBox(height: 14),
      Wrap(spacing: 6, runSpacing: 6, children: [
        for (final a in r.nextActions.where((a) => a.action != 'feedback' && a.action != 'ask_user'))
          ActionChip(label: Text(a.label), onPressed: () => runAction(a)),
      ]),
      const SizedBox(height: 18),
      Text('Was this good advice?'.toUpperCase(), style: DmText.eyebrow),
      const SizedBox(height: 8),
      Row(children: [
        Expanded(
          child: DmButton('Good advice', kind: DmButtonKind.dark, onPressed: () async {
            await notifier.feedback(liked: true);
            if (context.mounted) dmToast(context, 'Thanks, noted');
          }),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: DmButton('Not for me', kind: DmButtonKind.outline, onPressed: () async {
            await notifier.feedback(liked: false);
            if (context.mounted) dmToast(context, 'Noted, I will adapt');
          }),
        ),
      ]),
      const SizedBox(height: 8),
      DmButton('I bought it', kind: DmButtonKind.gold, icon: Icons.shopping_bag_outlined, onPressed: () async {
        await notifier.feedback(bought: true);
        ref.invalidate(checkinsProvider(userId));
        if (context.mounted) dmToast(context, 'Enjoy it! Later I will ask how often you wore it');
      }),
    ]);
  }
}

class _ScoreRing extends StatelessWidget {
  const _ScoreRing({required this.score, required this.color});

  final int score;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 76,
      height: 76,
      child: Stack(alignment: Alignment.center, children: [
        SizedBox.expand(
          child: CircularProgressIndicator(value: score / 100, strokeWidth: 7, color: color, backgroundColor: DmColors.sand),
        ),
        Text('$score', style: DmText.title.copyWith(fontSize: 24)),
      ]),
    );
  }
}

class _ContributionBar extends StatelessWidget {
  const _ContributionBar({required this.label, required this.value});

  final String label;
  final double value; // about -100..+100

  @override
  Widget build(BuildContext context) {
    final share = (value.abs() / 60).clamp(0.04, 1.0);
    final good = value >= 0;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(children: [
        SizedBox(width: 150, child: Text(label, style: DmText.body.copyWith(fontSize: 11.5), maxLines: 2)),
        Expanded(
          child: Row(children: [
            Expanded(
              child: Align(
                alignment: Alignment.centerRight,
                child: FractionallySizedBox(
                  widthFactor: good ? 0 : share,
                  child: Container(height: 8, decoration: BoxDecoration(color: _critical, borderRadius: BorderRadius.circular(4))),
                ),
              ),
            ),
            Container(width: 1, height: 14, color: DmColors.borderStrong),
            Expanded(
              child: Align(
                alignment: Alignment.centerLeft,
                child: FractionallySizedBox(
                  widthFactor: good ? share : 0,
                  child: Container(height: 8, decoration: BoxDecoration(color: DmColors.success, borderRadius: BorderRadius.circular(4))),
                ),
              ),
            ),
          ]),
        ),
      ]),
    );
  }
}

class _ShopTile extends ConsumerWidget {
  const _ShopTile({required this.link, required this.userId});

  final BuyLink link;
  final String userId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return SizedBox(
      width: 158,
      child: DmCard(
        padding: EdgeInsets.zero,
        onTap: () async {
          ref.read(smartBuyRepositoryProvider).click(link, userId);
          await launchUrl(Uri.parse(link.url), mode: LaunchMode.externalApplication);
        },
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          ClipRRect(
            borderRadius: const BorderRadius.vertical(top: Radius.circular(DmRadius.card)),
            child: link.imageUrl == null
                ? Container(height: 128, color: DmColors.sand, child: const Center(child: Icon(Icons.checkroom, color: DmColors.bronze)))
                : Image.network(link.imageUrl!, height: 128, width: double.infinity, fit: BoxFit.cover,
                    errorBuilder: (_, __, ___) => Container(height: 128, color: DmColors.sand)),
          ),
          Padding(
            padding: const EdgeInsets.all(10),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(link.item, style: DmText.itemName, maxLines: 2, overflow: TextOverflow.ellipsis),
              const SizedBox(height: 2),
              Text([link.shop, if (link.city != null) link.city!.split(';').first].join(' · '), style: DmText.caption, maxLines: 1, overflow: TextOverflow.ellipsis),
              const SizedBox(height: 4),
              Row(children: [
                Text('${link.priceTnd.toStringAsFixed(link.priceTnd % 1 == 0 ? 0 : 2)} TND', style: DmText.price),
                if (link.savedPct != null) ...[
                  const SizedBox(width: 6),
                  Text('−${link.savedPct} %', style: DmText.caption.copyWith(color: DmColors.success, fontWeight: FontWeight.w700)),
                ],
              ]),
            ]),
          ),
        ]),
      ),
    );
  }
}

class _ShoppingListSheet extends ConsumerWidget {
  const _ShoppingListSheet({required this.userId});

  final String userId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final list = ref.watch(shoppingListProvider(userId));
    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.75,
      builder: (_, controller) => ListView(
        controller: controller,
        padding: const EdgeInsets.all(20),
        children: [
          const DmSectionHeader(eyebrow: 'My shopping list', title: 'What you really miss'),
          const SizedBox(height: 14),
          ...list.when(
            loading: () => [const Center(child: CircularProgressIndicator())],
            error: (e, _) => [Text('$e', style: DmText.body)],
            data: (items) => items.isEmpty
                ? [const DmEmptyState(title: 'Nothing missing', message: 'Your wardrobe covers your goals.')]
                : [
                    for (final it in items)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: DmCard(
                          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            Row(children: [
                              Expanded(child: Text(it.piece, style: DmText.cardTitle)),
                              if (it.typicalPrice != null) DmPill('≈ ${it.typicalPrice!.round()} TND', dark: it.withinBudget == false),
                            ]),
                            const SizedBox(height: 4),
                            Text('${it.why} · ${it.newOutfits} new outfits', style: DmText.body),
                            for (final l in it.links)
                              TextButton(
                                onPressed: () => launchUrl(Uri.parse(l.url), mode: LaunchMode.externalApplication),
                                child: Text('${l.shop} · ${l.priceTnd.round()} TND →'),
                              ),
                          ]),
                        ),
                      ),
                  ],
          ),
        ],
      ),
    );
  }
}

/// Check-in icon with a dot when a "did you wear it?" question is waiting.
class _CheckinBadge extends ConsumerWidget {
  const _CheckinBadge({required this.userId});

  final String userId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final n = ref.watch(checkinsProvider(userId)).valueOrNull?.length ?? 0;
    return Badge(
      isLabelVisible: n > 0,
      label: Text('$n'),
      backgroundColor: DmColors.gold,
      child: const Icon(Icons.event_available_outlined, color: Colors.white),
    );
  }
}

/// Wishlist: pieces Smart Buy watches + price alerts from local shops.
class _WishlistSheet extends ConsumerStatefulWidget {
  const _WishlistSheet({required this.userId});

  final String userId;

  @override
  ConsumerState<_WishlistSheet> createState() => _WishlistSheetState();
}

class _WishlistSheetState extends ConsumerState<_WishlistSheet> {
  List<PriceAlert>? _alerts;
  bool _checking = false;

  Future<void> _check() async {
    setState(() => _checking = true);
    try {
      final a = await ref.read(smartBuyRepositoryProvider).checkPrices(widget.userId);
      setState(() => _alerts = a);
    } catch (_) {
      if (mounted) dmToast(context, 'Could not check the prices');
    } finally {
      if (mounted) setState(() => _checking = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final list = ref.watch(wishlistProvider(widget.userId));
    final repo = ref.read(smartBuyRepositoryProvider);
    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.75,
      builder: (_, controller) => ListView(
        controller: controller,
        padding: const EdgeInsets.all(20),
        children: [
          const DmSectionHeader(eyebrow: 'Price watch', title: 'My wishlist'),
          const SizedBox(height: 12),
          DmButton(_checking ? 'Checking local shops…' : 'Check prices now', kind: DmButtonKind.gold, icon: Icons.search_rounded,
              onPressed: _checking ? null : _check),
          if (_alerts != null) ...[
            const SizedBox(height: 12),
            if (_alerts!.isEmpty) Text('No price drop yet. I keep watching.', style: DmText.body),
            for (final a in _alerts!)
              Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: DmColors.warningBg,
                    borderRadius: BorderRadius.circular(DmRadius.card),
                    border: Border.all(color: DmColors.gold),
                  ),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text('Price drop'.toUpperCase(), style: DmText.eyebrow),
                    const SizedBox(height: 4),
                    Text(a.message, style: DmText.body.copyWith(color: DmColors.text)),
                    const SizedBox(height: 8),
                    DmButton('Open ${a.offer.shop}', kind: DmButtonKind.dark, onPressed: () {
                      repo.click(a.offer, widget.userId);
                      launchUrl(Uri.parse(a.offer.url), mode: LaunchMode.externalApplication);
                    }),
                  ]),
                ),
              ),
          ],
          const SizedBox(height: 16),
          ...list.when(
            loading: () => [const Center(child: CircularProgressIndicator())],
            error: (e, _) => [Text('$e', style: DmText.body)],
            data: (items) => items.isEmpty
                ? [const DmEmptyState(icon: Icons.favorite_border_rounded, title: 'Nothing watched yet', message: 'When I say THINK, tap "Watch the price" and I tell you when it drops.')]
                : [
                    for (final w in items)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: DmCard(
                          child: Row(children: [
                            Expanded(
                              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                Text(w.label, style: DmText.cardTitle),
                                const SizedBox(height: 2),
                                Text('Seen at ${w.priceTnd.round()} TND · alert at ${w.targetTnd.round()} TND or less', style: DmText.body),
                              ]),
                            ),
                            IconButton(
                              tooltip: 'Remove',
                              icon: const Icon(Icons.close_rounded),
                              onPressed: () async {
                                await repo.removeWish(widget.userId, w.id);
                                ref.invalidate(wishlistProvider(widget.userId));
                              },
                            ),
                          ]),
                        ),
                      ),
                  ],
          ),
        ],
      ),
    );
  }
}

/// "Did you wear it?" — the answers become real labels to retrain Smart Buy.
class _CheckinSheet extends ConsumerWidget {
  const _CheckinSheet({required this.userId});

  final String userId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final due = ref.watch(checkinsProvider(userId));
    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.6,
      builder: (_, controller) => ListView(
        controller: controller,
        padding: const EdgeInsets.all(20),
        children: [
          const DmSectionHeader(eyebrow: 'Wear check-in', title: 'Did you wear it?'),
          const SizedBox(height: 6),
          Text('Your answers teach Smart Buy what you really wear.', style: DmText.body),
          const SizedBox(height: 14),
          ...due.when(
            loading: () => [const Center(child: CircularProgressIndicator())],
            error: (e, _) => [Text('$e', style: DmText.body)],
            data: (items) => items.isEmpty
                ? [const DmEmptyState(icon: Icons.event_available_outlined, title: 'Nothing to ask', message: 'Tap "I bought it" after a verdict; I ask you later how often you wore it.')]
                : [for (final d in items) _CheckinCard(userId: userId, due: d)],
          ),
        ],
      ),
    );
  }
}

class _CheckinCard extends ConsumerStatefulWidget {
  const _CheckinCard({required this.userId, required this.due});

  final String userId;
  final CheckinDue due;

  @override
  ConsumerState<_CheckinCard> createState() => _CheckinCardState();
}

class _CheckinCardState extends ConsumerState<_CheckinCard> {
  final _answer = TextEditingController();
  String? _retry;
  bool _sending = false;

  @override
  void dispose() {
    _answer.dispose();
    super.dispose();
  }

  Future<void> _send(String text) async {
    if (text.trim().isEmpty) return;
    setState(() => _sending = true);
    try {
      final r = await ref.read(smartBuyRepositoryProvider).answerCheckin(userId: widget.userId, decisionId: widget.due.decisionId, answer: text);
      if (!r.saved) {
        setState(() => _retry = r.question);
        return;
      }
      ref.invalidate(checkinsProvider(widget.userId));
      if (mounted) {
        dmToast(context, r.adviceWasRight == true
            ? 'Thanks! Worn ${r.timesWorn}×: my advice was right'
            : 'Thanks! Worn ${r.timesWorn}×: I learn from this');
      }
    } catch (_) {
      if (mounted) dmToast(context, 'Could not save, try again');
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: DmCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text(widget.due.question, style: DmText.cardTitle),
          if (_retry != null) ...[
            const SizedBox(height: 4),
            Text(_retry!, style: DmText.body.copyWith(color: DmColors.warning)),
          ],
          const SizedBox(height: 10),
          Wrap(spacing: 6, runSpacing: 6, children: [
            for (final q in const ['Never', 'Once', 'A few times', 'Every week'])
              DmChoiceChip(label: q, selected: false, onTap: _sending ? () {} : () => _send(q)),
          ]),
          const SizedBox(height: 10),
          TextField(
            controller: _answer,
            decoration: InputDecoration(
              hintText: 'Or say it your way: "twice", "jamais", "barcha"…',
              suffixIcon: IconButton(icon: const Icon(Icons.send_rounded), onPressed: _sending ? null : () => _send(_answer.text)),
            ),
            onSubmitted: _send,
          ),
        ]),
      ),
    );
  }
}
