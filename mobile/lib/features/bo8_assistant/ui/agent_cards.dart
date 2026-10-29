// Owner: BO8 (Nadhir) — every agent's answer drawn in the chat the way its own screen shows it:
// Smart Buy verdict ring (BO5), outfits with your pieces (BO1/BO2), shop products (BO6), wardrobe pieces
// (BO4), challenges (BO7), style profile (BO4 · M5). Unknown shapes fall back to key facts.
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/api/dm_api.dart';
import '../../../core/design/dressme_design.dart';
import '../../../core/widgets/outfit_strip.dart';

/// The agent result with its inner `result` merged in (agents answer {result: {...}} or flat).
Json _flat(Json card) {
  final inner = card['result'];
  return inner is Map ? {...card, ...inner.cast<String, dynamic>()} : card;
}

class AgentCardView extends StatelessWidget {
  const AgentCardView({super.key, required this.card, required this.api});

  final Json card;
  final DmApi api;

  @override
  Widget build(BuildContext context) {
    final d = _flat(card);
    final parts = <Widget>[
      if (d['verdict'] != null) _Verdict(d: d),
      if (jsonList(d['results']).isNotEmpty || jsonList(d['products']).isNotEmpty)
        _Products(items: jsonList(d['results']).isNotEmpty ? jsonList(d['results']) : jsonList(d['products']), api: api),
      if (d['verdict'] == null) ..._outfits(d),
      if (jsonList(d['items']).isNotEmpty && d['verdict'] == null && jsonList(d['outfits']).isEmpty) _Pieces(items: jsonList(d['items']), api: api),
      if (jsonList(d['challenges']).isNotEmpty) _Challenges(items: jsonList(d['challenges'])),
      if (jsonList(d['top_styles']).isNotEmpty) _Styles(items: jsonList(d['top_styles'])),
    ];
    if (parts.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 10),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        for (final p in parts) Padding(padding: const EdgeInsets.only(bottom: 8), child: p),
      ]),
    );
  }

  List<Widget> _outfits(Json d) {
    final outs = outfitIdsIn({'outfits': d['outfits'], 'item_ids': d['item_ids'], 'outfit': d['outfit']});
    return [
      for (final (i, ids) in outs.take(2).indexed)
        _Box(
          title: i == 0 ? 'Proposed outfit' : 'Alternative',
          icon: Icons.auto_awesome_outlined,
          child: OutfitStrip(ids: ids, size: 60),
        ),
    ];
  }
}

class _Box extends StatelessWidget {
  const _Box({required this.title, required this.icon, required this.child});

  final String title;
  final IconData icon;
  final Widget child;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: DmColors.page,
          borderRadius: BorderRadius.circular(DmRadius.card),
          border: Border.all(color: DmColors.border),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Icon(icon, size: 16, color: DmColors.bronze),
            const SizedBox(width: 6),
            Text(title.toUpperCase(), style: DmText.eyebrow),
          ]),
          const SizedBox(height: 8),
          child,
        ]),
      );
}

/// Smart Buy (BO5): the score ring, BUY / THINK / SKIP, the explanation, and where to go next.
class _Verdict extends StatelessWidget {
  const _Verdict({required this.d});

  final Json d;

  @override
  Widget build(BuildContext context) {
    final v = '${d['verdict']}'.toLowerCase();
    final (word, color) = switch (v) {
      'buy' => ('BUY', DmColors.success),
      'think' => ('THINK', DmColors.warning),
      _ => ('SKIP', const Color(0xFFA2453A)),
    };
    final raw = (d['score'] as num?)?.toDouble() ?? 0;
    final score = raw <= 1 ? raw * 100 : raw;
    final sub = d['subcategory'] ?? (d['candidate'] as Map?)?['subcategory'];
    final colour = d['colour'] ?? (d['candidate'] as Map?)?['colour'];
    final text = d['explanation'] ?? d['why'] ?? d['reason'];
    return _Box(
      title: 'Smart Buy',
      icon: Icons.shopping_bag_outlined,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          SizedBox(
            width: 64,
            height: 64,
            child: TweenAnimationBuilder<double>(
              tween: Tween(begin: 0, end: score / 100),
              duration: const Duration(milliseconds: 700),
              builder: (_, t, __) => CustomPaint(
                painter: _Ring(t, color),
                child: Center(child: Text('${score.round()}', style: DmText.title.copyWith(fontSize: 20))),
              ),
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              if (d['piece'] != null || sub != null) Text('${d['piece'] ?? '$colour $sub'}'.toUpperCase(), style: DmText.eyebrow),
              Text(word, style: DmText.display.copyWith(color: color, fontSize: 28)),
            ]),
          ),
        ]),
        if (text != null) ...[const SizedBox(height: 8), Text('$text', style: DmText.body)],
        if (sub != null)
          Wrap(spacing: 4, children: [
            TextButton.icon(
              onPressed: () => context.go('/bo9_avatar?try=${Uri.encodeComponent('$sub|${colour ?? ''}')}'),
              icon: const Icon(Icons.view_in_ar_outlined, size: 18),
              label: const Text('Try it on'),
            ),
            if (v != 'buy')
              TextButton.icon(
                onPressed: () => context.go('/bo6_local_market?q=${Uri.encodeComponent('${colour ?? ''} $sub'.trim())}'),
                icon: const Icon(Icons.storefront_outlined, size: 18),
                label: const Text('Find it cheaper'),
              ),
            TextButton.icon(
              onPressed: () => context.go('/bo5_smart_buy?type=${Uri.encodeComponent('$sub')}&colour=${Uri.encodeComponent('${colour ?? ''}')}'),
              icon: const Icon(Icons.open_in_new_rounded, size: 18),
              label: const Text('Open Smart Buy'),
            ),
          ]),
      ]),
    );
  }
}

class _Ring extends CustomPainter {
  _Ring(this.t, this.color);

  final double t;
  final Color color;

  @override
  void paint(Canvas canvas, Size s) {
    final rect = Offset.zero & s;
    final bg = Paint()
      ..color = DmColors.border
      ..style = PaintingStyle.stroke
      ..strokeWidth = 6;
    final fg = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 6
      ..strokeCap = StrokeCap.round;
    canvas.drawArc(rect.deflate(4), 0, 2 * math.pi, false, bg);
    canvas.drawArc(rect.deflate(4), -math.pi / 2, 2 * math.pi * t.clamp(0, 1), false, fg);
  }

  @override
  bool shouldRepaint(_Ring old) => old.t != t || old.color != color;
}

/// Local shops (BO6 · M7): product cards with photo, shop and price.
class _Products extends StatelessWidget {
  const _Products({required this.items, required this.api});

  final List<Json> items;
  final DmApi api;

  @override
  Widget build(BuildContext context) => _Box(
        title: 'In local shops',
        icon: Icons.storefront_outlined,
        child: SizedBox(
          height: 190,
          child: ListView(scrollDirection: Axis.horizontal, children: [
            for (final p in items.take(8))
              GestureDetector(
                onTap: () {
                  final url = p['product_url'] ?? p['url'];
                  if (url != null) launchUrl(Uri.parse('$url'), mode: LaunchMode.externalApplication);
                },
                child: Container(
                  width: 130,
                  margin: const EdgeInsets.only(right: 8),
                  decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12), border: Border.all(color: DmColors.border)),
                  clipBehavior: Clip.antiAlias,
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Expanded(
                      child: Container(
                        color: DmColors.sand,
                        width: double.infinity,
                        child: (p['image_url'] ?? p['image']) == null
                            ? const Icon(Icons.checkroom, color: DmColors.bronze)
                            : Image.network(api.media('${p['image_url'] ?? p['image']}'), fit: BoxFit.cover,
                                errorBuilder: (_, __, ___) => const Icon(Icons.checkroom, color: DmColors.bronze)),
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.all(8),
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text('${p['item'] ?? p['name'] ?? p['title'] ?? ''}', style: DmText.caption.copyWith(color: DmColors.text, fontWeight: FontWeight.w600),
                            maxLines: 2, overflow: TextOverflow.ellipsis),
                        Text('${p['shop'] ?? ''}', style: DmText.caption, maxLines: 1, overflow: TextOverflow.ellipsis),
                        if (p['price_tnd'] != null) Text('${(p['price_tnd'] as num).round()} TND', style: DmText.cardTitle.copyWith(fontSize: 14)),
                      ]),
                    ),
                  ]),
                ),
              ),
          ]),
        ),
      );
}

/// Wardrobe (BO4 · M1): the pieces with their cut-outs.
class _Pieces extends StatelessWidget {
  const _Pieces({required this.items, required this.api});

  final List<Json> items;
  final DmApi api;

  @override
  Widget build(BuildContext context) {
    final ids = [for (final it in items.take(12)) if (it['item_id'] != null) '${it['item_id']}'];
    return _Box(
      title: 'Your wardrobe · ${items.length} pieces',
      icon: Icons.checkroom,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        OutfitStrip(ids: ids, size: 56, tryOn: false),
        TextButton.icon(
          onPressed: () => context.go('/bo4_style'),
          icon: const Icon(Icons.open_in_new_rounded, size: 18),
          label: const Text('Open my wardrobe'),
        ),
      ]),
    );
  }
}

/// Challenges (BO7 · M15).
class _Challenges extends StatelessWidget {
  const _Challenges({required this.items});

  final List<Json> items;

  @override
  Widget build(BuildContext context) => _Box(
        title: 'Challenges',
        icon: Icons.emoji_events_outlined,
        child: Column(children: [
          for (final c in items.take(4))
            ListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.emoji_events_outlined, color: DmColors.gold),
              title: Text('${c['title'] ?? c['name'] ?? c['id']}', style: DmText.body.copyWith(fontWeight: FontWeight.w600)),
              subtitle: c['description'] != null || c['rules'] != null
                  ? Text('${c['description'] ?? c['rules']}', maxLines: 2, overflow: TextOverflow.ellipsis, style: DmText.caption)
                  : null,
              trailing: const Icon(Icons.chevron_right_rounded),
              onTap: () => context.go('/bo7_sharing'),
            ),
        ]),
      );
}

/// Style profile (BO4 · M5): the styles learnt from the swipes.
class _Styles extends StatelessWidget {
  const _Styles({required this.items});

  final List<Json> items;

  @override
  Widget build(BuildContext context) => _Box(
        title: 'Your style',
        icon: Icons.style_outlined,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Wrap(spacing: 6, runSpacing: 6, children: [
            for (final s in items.take(5)) Chip(label: Text('${s['style']} · ${pct(s['share'])}', style: DmText.caption)),
          ]),
          TextButton.icon(
            onPressed: () => context.go('/my_style'),
            icon: const Icon(Icons.open_in_new_rounded, size: 18),
            label: const Text('Open My style'),
          ),
        ]),
      );
}
