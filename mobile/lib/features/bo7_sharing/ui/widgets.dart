// Owner: BO7 — shared widgets of the BO7 screens, in the DressMe design (core/design/dressme_design.dart).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/design/dressme_design.dart';
import '../data/bo7_models.dart';
import '../logic/bo7_providers.dart';

Color hexColor(String? hex, [Color fallback = const Color(0xFFC9C6CC)]) {
  final h = (hex ?? '').replaceAll('#', '');
  if (h.length != 6) return fallback;
  final v = int.tryParse(h, radix: 16);
  return v == null ? fallback : Color(0xFF000000 | v);
}

void showSnack(BuildContext context, String message) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(message)));
}

Future<void> openLink(BuildContext context, String url) async {
  final ok = await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
  if (!ok && context.mounted) showSnack(context, 'Impossible d\'ouvrir le lien');
}

/// Dark header of every tab: gold eyebrow, serif title, light subtitle, gold glow (Figma prototype).
class Bo7Hero extends StatelessWidget {
  const Bo7Hero({super.key, required this.eyebrow, required this.title, this.subtitle, this.trailing});

  final String eyebrow;
  final String title;
  final String? subtitle;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Container(
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(color: DmColors.ink, borderRadius: BorderRadius.circular(DmRadius.hero)),
      child: Stack(
        children: [
          Positioned(
            right: -60,
            top: -80,
            child: Container(
              width: 220,
              height: 220,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(
                  colors: [DmColors.gold.withValues(alpha: 0.35), DmColors.gold.withValues(alpha: 0)],
                ),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(22, 22, 22, 22),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(eyebrow.toUpperCase(), style: DmText.eyebrow.copyWith(color: DmColors.gold)),
                const SizedBox(height: 8),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Expanded(child: Text(title, style: DmText.display.copyWith(color: Colors.white, fontSize: 30))),
                    if (trailing != null) trailing!,
                  ],
                ),
                if (subtitle != null) ...[
                  const SizedBox(height: 8),
                  Text(subtitle!,
                      style: DmText.body.copyWith(color: Colors.white.withValues(alpha: 0.6), fontSize: 13)),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// White rounded panel with an optional serif title.
class Bo7Panel extends StatelessWidget {
  const Bo7Panel({super.key, this.title, this.subtitle, required this.child, this.trailing});

  final String? title;
  final String? subtitle;
  final Widget child;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: DmColors.surface,
        borderRadius: BorderRadius.circular(DmRadius.panel),
        border: Border.all(color: DmColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (title != null)
            Row(
              children: [
                Expanded(child: Text(title!, style: DmText.cardTitle)),
                if (trailing != null) trailing!,
              ],
            ),
          if (subtitle != null) ...[
            const SizedBox(height: 4),
            Text(subtitle!, style: DmText.body),
          ],
          if (title != null || subtitle != null) const SizedBox(height: 12),
          child,
        ],
      ),
    );
  }
}

/// Loading / error / data, with a retry button on errors (server not started, etc.).
class AsyncBody<T> extends StatelessWidget {
  const AsyncBody({super.key, required this.value, required this.builder, this.onRetry, this.compact = false});

  final AsyncValue<T> value;
  final Widget Function(T data) builder;
  final VoidCallback? onRetry;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return value.when(
      data: builder,
      loading: () => Padding(
        padding: EdgeInsets.all(compact ? 12 : 40),
        child: const Center(child: CircularProgressIndicator(strokeWidth: 2.4)),
      ),
      error: (e, _) => Padding(
        padding: EdgeInsets.all(compact ? 8 : 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(e.toString(), textAlign: TextAlign.center, style: DmText.body.copyWith(color: DmColors.warning)),
            if (onRetry != null) ...[
              const SizedBox(height: 10),
              OutlinedButton(onPressed: onRetry, child: const Text('Réessayer')),
            ],
          ],
        ),
      ),
    );
  }
}

/// Photo of a garment (from M1), or a soft colour block when there is no photo.
class GarmentImage extends ConsumerWidget {
  const GarmentImage(this.garment, {super.key, this.fit = BoxFit.contain});

  final Garment garment;
  final BoxFit fit;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final placeholder = Center(
      child: Icon(Icons.checkroom_rounded, size: 34, color: hexColor(garment.colorHex).withValues(alpha: 0.9)),
    );
    final path = garment.photoUrl;
    if (path == null || path.isEmpty) return placeholder;
    return Image.network(
      ref.read(bo7RepositoryProvider).url(path),
      fit: fit,
      errorBuilder: (_, __, ___) => placeholder,
    );
  }
}

/// Selectable garment tile (pickers of the challenges and of the studio).
class GarmentTile extends StatelessWidget {
  const GarmentTile(
      {super.key, required this.garment, required this.selected, required this.onTap, this.dimmed = false});

  final Garment garment;
  final bool selected;
  final bool dimmed;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Opacity(
      opacity: dimmed ? 0.35 : 1,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(DmRadius.card),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 160),
          padding: const EdgeInsets.all(6),
          decoration: BoxDecoration(
            color: DmColors.surface,
            borderRadius: BorderRadius.circular(DmRadius.card),
            border: Border.all(color: selected ? DmColors.bronze : DmColors.border, width: selected ? 2 : 1),
          ),
          child: Stack(
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Container(
                      width: double.infinity,
                      decoration:
                          BoxDecoration(color: DmColors.canvas, borderRadius: BorderRadius.circular(DmRadius.small)),
                      padding: const EdgeInsets.all(4),
                      child: GarmentImage(garment),
                    ),
                  ),
                  const SizedBox(height: 5),
                  Text(garment.name,
                      maxLines: 1, overflow: TextOverflow.ellipsis, style: DmText.itemName.copyWith(fontSize: 11)),
                  Text(
                    garment.isTunisian ? garment.localTag! : (garment.color ?? categoryLabels[garment.category] ?? ''),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: DmText.caption.copyWith(color: garment.isTunisian ? DmColors.bronze : DmColors.muted),
                  ),
                ],
              ),
              if (selected)
                const Positioned(
                  top: 4,
                  right: 4,
                  child: CircleAvatar(
                    radius: 11,
                    backgroundColor: DmColors.bronze,
                    child: Icon(Icons.check, size: 14, color: Colors.white),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Horizontal row of pill chips (category filters, card types...).
class PillChoice<T> extends StatelessWidget {
  const PillChoice(
      {super.key, required this.options, required this.selected, required this.label, required this.onSelected});

  final List<T> options;
  final T selected;
  final String Function(T) label;
  final ValueChanged<T> onSelected;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          for (final o in options)
            Padding(
              padding: const EdgeInsets.only(right: 6),
              child: ChoiceChip(
                label: Text(label(o)),
                selected: o == selected,
                onSelected: (_) => onSelected(o),
              ),
            ),
        ],
      ),
    );
  }
}

/// Grid of garments to pick from, filtered by category and Tunisian makers.
class GarmentPicker extends StatefulWidget {
  const GarmentPicker({
    super.key,
    required this.garments,
    required this.selected,
    required this.onToggle,
    this.height = 300,
  });

  final List<Garment> garments;
  final Set<String> selected;
  final ValueChanged<Garment> onToggle;
  final double height;

  @override
  State<GarmentPicker> createState() => _GarmentPickerState();
}

class _GarmentPickerState extends State<GarmentPicker> {
  String _cat = 'all';

  @override
  Widget build(BuildContext context) {
    final cats = ['all', ...categoryOrder.where((c) => widget.garments.any((g) => g.category == c)), 'tn'];
    final shown = widget.garments.where((g) {
      if (_cat == 'tn') return g.isTunisian;
      return _cat == 'all' || g.category == _cat;
    }).toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        PillChoice<String>(
          options: cats,
          selected: _cat,
          label: (c) => c == 'tn' ? 'Créateurs tunisiens' : (categoryLabels[c] ?? c),
          onSelected: (c) => setState(() => _cat = c),
        ),
        const SizedBox(height: 10),
        SizedBox(
          height: widget.height,
          child: shown.isEmpty
              ? const Center(child: Text('Aucune pièce ici.', style: DmText.body))
              : GridView.builder(
                  gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
                    maxCrossAxisExtent: 120,
                    mainAxisExtent: 150,
                    crossAxisSpacing: 8,
                    mainAxisSpacing: 8,
                  ),
                  itemCount: shown.length,
                  itemBuilder: (_, i) => GarmentTile(
                    garment: shown[i],
                    selected: widget.selected.contains(shown[i].id),
                    onTap: () => widget.onToggle(shown[i]),
                  ),
                ),
        ),
      ],
    );
  }
}

/// "How it works": the agent's pipeline, Input → Code → Output (point 5 of the presentation).
void showPipeline(BuildContext context, String title, List<PipelineStep> steps) {
  showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    builder: (_) => DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.7,
      builder: (_, controller) => ListView(
        controller: controller,
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 30),
        children: [
          const Text('COMMENT ÇA MARCHE', style: DmText.eyebrow),
          Text(title, style: DmText.title),
          const SizedBox(height: 14),
          for (final (i, s) in steps.indexed)
            Container(
              margin: const EdgeInsets.only(bottom: 8),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: DmColors.surface,
                borderRadius: BorderRadius.circular(DmRadius.card),
                border: Border.all(color: DmColors.border),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  CircleAvatar(
                    radius: 13,
                    backgroundColor: s.stage == 'code' ? DmColors.ink : DmColors.gold,
                    child: Text('${i + 1}',
                        style: const TextStyle(fontSize: 11, color: Colors.white, fontWeight: FontWeight.w700)),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(child: Text(s.name, style: DmText.itemName.copyWith(fontSize: 13))),
                            DmPill(s.method),
                          ],
                        ),
                        const SizedBox(height: 3),
                        Text(s.detail, style: DmText.body),
                      ],
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    ),
  );
}

/// Small number tile (points, streak, KPIs).
class StatTile extends StatelessWidget {
  const StatTile(this.value, this.label, {super.key, this.dark = false});

  final String value;
  final String label;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: dark ? DmColors.ink : DmColors.sand,
        borderRadius: BorderRadius.circular(DmRadius.card),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(value, style: DmText.title.copyWith(fontSize: 22, color: dark ? DmColors.gold : DmColors.ink)),
          Text(label, style: DmText.caption.copyWith(color: dark ? Colors.white70 : DmColors.muted)),
        ],
      ),
    );
  }
}

/// Round avatar with the user's initials.
class UserAvatar extends StatelessWidget {
  const UserAvatar(this.userId, {super.key, this.radius = 17});

  final String userId;
  final double radius;

  static const _colors = [
    DmColors.ink,
    Color(0xFFB0573E),
    Color(0xFF5E7A55),
    DmColors.bronze,
    Color(0xFF7A5C6E),
    Color(0xFF4F6A73)
  ];

  @override
  Widget build(BuildContext context) {
    final c = _colors[userId.codeUnits.fold<int>(0, (a, b) => a + b) % _colors.length];
    final initials = userId.replaceAll(RegExp(r'[^A-Za-z0-9]'), '').toUpperCase();
    return CircleAvatar(
      radius: radius,
      backgroundColor: c,
      child: Text(
        initials.length >= 2 ? initials.substring(0, 2) : initials,
        style: TextStyle(color: Colors.white, fontSize: radius * 0.7, fontWeight: FontWeight.w700),
      ),
    );
  }
}
