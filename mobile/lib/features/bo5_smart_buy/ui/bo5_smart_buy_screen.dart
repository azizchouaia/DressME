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

const _typeFr = {
  'shirt': 'Chemise', 't-shirt': 'T-shirt', 'sweater': 'Pull', 'blouse': 'Blouse', 'jeans': 'Jean', 'chinos': 'Chino',
  'trousers': 'Pantalon', 'skirt': 'Jupe', 'sneakers': 'Baskets', 'loafers': 'Mocassins', 'boots': 'Bottes',
  'sandals': 'Sandales', 'jacket': 'Veste', 'coat': 'Manteau', 'blazer': 'Blazer', 'dress': 'Robe', 'jebba': 'Jebba',
};
const _colourFr = {
  'white': 'blanc', 'black': 'noir', 'grey': 'gris', 'navy': 'marine', 'beige': 'beige', 'brown': 'marron',
  'camel': 'camel', 'blue': 'bleu', 'olive': 'olive', 'red': 'rouge', 'pink': 'rose', 'green': 'vert',
  'burgundy': 'bordeaux', 'mustard': 'moutarde',
};
const _critical = Color(0xFFA2453A); // SKIP (not in the kit: verdict colour of BO5 only)

({String word, String sub, Color color}) _verdictStyle(String v) => switch (v) {
      'buy' => (word: 'Achète-la', sub: 'Bon achat pour ta garde-robe', color: DmColors.success),
      'think' => (word: 'Réfléchis', sub: 'À peser avant de payer', color: DmColors.warning),
      _ => (word: 'Passe ton tour', sub: 'Tu as déjà ce qu’il faut', color: _critical),
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
  String _lang = 'fr';
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
      setState(() => _photoError = 'Je n’ai pas pu lire la photo. Choisis le type et la couleur toi-même.');
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
            title: 'Le serveur ne répond pas',
            message: 'Lance l’API (uvicorn api.main:app) puis réessaie.\n${smartBuyApiUrl()}',
            action: DmButton('Réessayer', onPressed: () => ref.invalidate(smartBuyMetaProvider)),
          ),
        ),
        data: (m) => ListView(
          padding: EdgeInsets.zero,
          children: [
            DmHero(
              eyebrow: 'Smart Buy · avant de payer',
              title: 'Dois-je l’acheter ?',
              trailing: IconButton(
                tooltip: 'Ma liste d’achats',
                onPressed: () => _showShoppingList(context),
                icon: const Icon(Icons.checklist_rounded, color: Colors.white),
              ),
              child: SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(children: [
                  for (final u in m.users)
                    Padding(
                      padding: const EdgeInsets.only(right: 8),
                      child: DmChoiceChip(
                        label: '${u.id.replaceFirst('usr_', '')} · ${u.items}',
                        selected: _user == u.id,
                        onDark: true,
                        onTap: () => setState(() => _user = u.id),
                      ),
                    ),
                ]),
              ),
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
                      result.isLoading ? 'Analyse en cours…' : 'Dois-je l’acheter ?',
                      kind: DmButtonKind.gold,
                      icon: Icons.auto_awesome,
                      onPressed: result.isLoading ? null : _judge,
                    ),
                    const SizedBox(height: 20),
                    result.when(
                      loading: () => const Padding(padding: EdgeInsets.all(32), child: Center(child: CircularProgressIndicator())),
                      error: (e, _) => DmCard(child: DmEmptyState(icon: Icons.error_outline, title: 'Oups', message: '$e')),
                      data: (r) => r == null
                          ? const DmCard(
                              child: DmEmptyState(
                                icon: Icons.shopping_bag_outlined,
                                title: 'Montre-moi la pièce',
                                message: 'Une photo ou un exemple, son prix, et je te dis si elle vaut le coup avec ce que tu as déjà.',
                              ),
                            )
                          : _ResultView(result: r, userId: _user),
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
        const DmSectionHeader(eyebrow: 'La pièce en boutique', title: 'Photo ou exemple'),
        const SizedBox(height: 14),
        Row(children: [
          Expanded(child: DmButton('Photo', icon: Icons.photo_camera_outlined, onPressed: () => _pickPhoto(ImageSource.camera))),
          const SizedBox(width: 8),
          Expanded(child: DmButton('Galerie', kind: DmButtonKind.outline, icon: Icons.image_outlined, onPressed: () => _pickPhoto(ImageSource.gallery))),
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
                  ? const Padding(padding: EdgeInsets.only(top: 12), child: Text('L’IA regarde la pièce…', style: DmText.body))
                  : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text('L’IA a vu — corrige si besoin'.toUpperCase(), style: DmText.eyebrow),
                      const SizedBox(height: 6),
                      if (_guess != null)
                        Wrap(spacing: 6, runSpacing: 6, children: [
                          DmPill('${_typeFr[_guess!.subcategory] ?? _guess!.subcategory} · ${(_guess!.typeConfidence * 100).round()} %'),
                          DmPill('${_colourFr[_guess!.colour] ?? _guess!.colour} · ${(_guess!.colourConfidence * 100).round()} %'),
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
              items: [for (final t in m.types.keys) DropdownMenuItem(value: t, child: Text(_typeFr[t] ?? t))],
              onChanged: (v) => setState(() => _type = v ?? _type),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: DropdownButtonFormField<String>(
              key: ValueKey('colour-$_type-$_colour'),
              initialValue: colours.contains(_colour) ? _colour : null,
              decoration: const InputDecoration(labelText: 'Couleur'),
              items: [
                for (final c in colours)
                  DropdownMenuItem(
                    value: c,
                    child: Row(children: [
                      Container(width: 12, height: 12, decoration: BoxDecoration(color: _hex(m.colours[c] ?? '#999999'), shape: BoxShape.circle, border: Border.all(color: DmColors.border))),
                      const SizedBox(width: 8),
                      Text(_colourFr[c] ?? c),
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
              decoration: const InputDecoration(labelText: 'Prix', suffixText: 'TND'),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: DropdownButtonFormField<String?>(
              initialValue: _brand,
              decoration: const InputDecoration(labelText: 'Marque (taille)'),
              items: [
                const DropdownMenuItem<String?>(value: null, child: Text('— aucune —')),
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
            labelText: 'Comment te vont tes vêtements ? (optionnel)',
            hintText: 'Ex. : je porte du M chez Medina Atelier, serré aux épaules',
          ),
        ),
        const SizedBox(height: 12),
        Row(children: [
          Text('Réponse en'.toUpperCase(), style: DmText.eyebrow),
          const SizedBox(width: 10),
          for (final (code, label) in const [('fr', 'Français'), ('en', 'English'), ('ar', 'Tounsi')])
            Padding(
              padding: const EdgeInsets.only(right: 6),
              child: DmChoiceChip(label: label, selected: _lang == code, onTap: () => setState(() => _lang = code)),
            ),
        ]),
      ]),
    );
  }

  void _showShoppingList(BuildContext context) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _ShoppingListSheet(userId: _user),
    );
  }
}

class _ResultView extends ConsumerWidget {
  const _ResultView({required this.result, required this.userId});

  final SmartBuyResult result;
  final String userId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final r = result;
    final v = _verdictStyle(r.verdict);
    final notifier = ref.read(smartBuyProvider.notifier);
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
          Text(r.explanationByAi ? 'Écrit par l’IA locale à partir des faits ci-dessous' : 'Texte modèle (IA locale éteinte)', style: DmText.caption),
          if (r.fillsGoal != null || r.newOutfits > 0) ...[
            const SizedBox(height: 12),
            Wrap(spacing: 6, runSpacing: 6, children: [
              if (r.newOutfits > 0) DmPill('${r.newOutfits} nouvelles tenues'),
              if (r.fillsGoal != null) DmPill('Objectif : ${r.fillsGoal}'),
              if (r.costPerWear != null) DmPill('${r.costPerWear!.toStringAsFixed(2)} TND / port'),
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
            Text('Pas sûr·e'.toUpperCase(), style: DmText.eyebrow),
            const SizedBox(height: 4),
            Text(r.question!, style: DmText.body.copyWith(color: DmColors.text, fontSize: 13)),
            if (r.questionKey != null) ...[
              const SizedBox(height: 10),
              Row(children: [
                DmButton('Oui', onPressed: () => notifier.answer(r.questionKey!, true)),
                const SizedBox(width: 8),
                DmButton('Non', kind: DmButtonKind.outline, onPressed: () => notifier.answer(r.questionKey!, false)),
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
          const DmSectionHeader(eyebrow: 'Pourquoi', title: 'Ce qui a pesé'),
          const SizedBox(height: 12),
          for (final e in r.contributions.entries.take(6)) _ContributionBar(label: e.key, value: e.value),
          const SizedBox(height: 4),
          Text('vert = vers « achète » · rouge = vers « passe ton tour »', style: DmText.caption),
          const SizedBox(height: 14),
          DmReasons(r.reasons.take(5).toList()),
          if (r.whatIf.isNotEmpty) ...[
            const Divider(height: 24),
            Text('Ce qui changerait la réponse'.toUpperCase(), style: DmText.eyebrow),
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
            const DmSectionHeader(eyebrow: 'Déjà dans ton placard', title: 'Pièces proches'),
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
                Text('Ta taille'.toUpperCase(), style: DmText.eyebrow),
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
        DmSectionHeader(eyebrow: r.links.first.isReal ? 'Boutiques tunisiennes' : 'Boutiques (exemple)', title: 'Acheter près de chez toi'),
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
      // 7. Memory + next steps + feedback
      if (r.memoryNotes.isNotEmpty) ...[
        const SizedBox(height: 14),
        DmCard(
          padding: const EdgeInsets.all(16),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('Smart Buy se souvient'.toUpperCase(), style: DmText.eyebrow),
            const SizedBox(height: 6),
            for (final n in r.memoryNotes) Text('• $n', style: DmText.body),
          ]),
        ),
      ],
      const SizedBox(height: 14),
      Wrap(spacing: 6, runSpacing: 6, children: [
        for (final a in r.nextActions.where((a) => a.action != 'feedback' && a.action != 'ask_user'))
          ActionChip(label: Text(a.label), onPressed: () => dmToast(context, 'Bientôt : ${a.tool ?? ''} via l’assistant')),
      ]),
      const SizedBox(height: 18),
      Text('Ce conseil t’aide ?'.toUpperCase(), style: DmText.eyebrow),
      const SizedBox(height: 8),
      Row(children: [
        Expanded(
          child: DmButton('Bon conseil', kind: DmButtonKind.dark, onPressed: () async {
            await notifier.feedback(liked: true);
            if (context.mounted) dmToast(context, 'Merci, je retiens');
          }),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: DmButton('Pas pour moi', kind: DmButtonKind.outline, onPressed: () async {
            await notifier.feedback(liked: false);
            if (context.mounted) dmToast(context, 'Noté, je m’adapte');
          }),
        ),
      ]),
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
              Text('${link.priceTnd.toStringAsFixed(link.priceTnd % 1 == 0 ? 0 : 2)} TND', style: DmText.price),
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
          const DmSectionHeader(eyebrow: 'Ma liste d’achats', title: 'Ce qui manque vraiment'),
          const SizedBox(height: 14),
          ...list.when(
            loading: () => [const Center(child: CircularProgressIndicator())],
            error: (e, _) => [Text('$e', style: DmText.body)],
            data: (items) => items.isEmpty
                ? [const DmEmptyState(title: 'Rien ne manque', message: 'Ta garde-robe couvre tes objectifs.')]
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
                            Text('${it.why} · ${it.newOutfits} nouvelles tenues', style: DmText.body),
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
