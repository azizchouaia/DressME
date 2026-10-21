// Shared DressMe widgets, built on lib/core/design/dressme_design.dart (Dm* tokens).
// Use these instead of re-styling the same pieces in every BO screen.
import 'package:flutter/material.dart';

import '../design/dressme_design.dart';

/// Dark top band of a screen (home hero style): eyebrow, serif title, optional content under it.
class DmHero extends StatelessWidget {
  const DmHero({super.key, required this.eyebrow, required this.title, this.trailing, this.child});

  final String eyebrow;
  final String title;
  final Widget? trailing;
  final Widget? child;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      color: DmColors.inkDeep,
      padding: const EdgeInsets.fromLTRB(20, 28, 20, 28),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(eyebrow.toUpperCase(),
                        style: DmText.eyebrow.copyWith(color: const Color(0xFFCDB18D), fontSize: 11, letterSpacing: 2.2)),
                    const SizedBox(height: 4),
                    Text(title, style: DmText.display.copyWith(color: Colors.white)),
                  ],
                ),
              ),
              if (trailing != null) trailing!,
            ],
          ),
          if (child != null) ...[const SizedBox(height: 18), child!],
        ],
      ),
    );
  }
}

/// White bordered card with the prototype's radius. [big] = the main card of a screen (28 + soft shadow).
class DmCard extends StatelessWidget {
  const DmCard({super.key, required this.child, this.big = false, this.padding = const EdgeInsets.all(16), this.onTap});

  final Widget child;
  final bool big;
  final EdgeInsetsGeometry padding;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final radius = BorderRadius.circular(big ? DmRadius.hero : DmRadius.card);
    return Container(
      decoration: BoxDecoration(
        color: DmColors.surface,
        borderRadius: radius,
        border: Border.all(color: DmColors.border),
        boxShadow: big
            ? const [BoxShadow(color: Color(0x1F2D2319), blurRadius: 50, offset: Offset(0, 18))]
            : null,
      ),
      child: Material(
        type: MaterialType.transparency,
        child: InkWell(borderRadius: radius, onTap: onTap, child: Padding(padding: padding, child: child)),
      ),
    );
  }
}

/// Choice chip: dark when selected. [onDark] = on the dark hero (gold when selected).
class DmChoiceChip extends StatelessWidget {
  const DmChoiceChip({super.key, required this.label, required this.selected, required this.onTap, this.onDark = false});

  final String label;
  final bool selected;
  final VoidCallback onTap;
  final bool onDark;

  @override
  Widget build(BuildContext context) {
    final Color bg, fg, line;
    if (onDark) {
      bg = selected ? DmColors.gold : Colors.white.withValues(alpha: 0.05);
      fg = selected ? DmColors.inkDeep : Colors.white.withValues(alpha: 0.65);
      line = selected ? DmColors.gold : Colors.white.withValues(alpha: 0.15);
    } else {
      bg = selected ? DmColors.ink : DmColors.surface;
      fg = selected ? Colors.white : DmColors.mutedDark;
      line = selected ? DmColors.ink : DmColors.borderStrong;
    }
    return Semantics(
      button: true,
      selected: selected,
      child: GestureDetector(
        onTap: onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          decoration: BoxDecoration(
            color: bg,
            borderRadius: BorderRadius.circular(DmRadius.pill),
            border: Border.all(color: line),
          ),
          child: Text(label, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: fg)),
        ),
      ),
    );
  }
}

/// The 3 button styles of the prototype: dark (main action), gold (AI action), outline (secondary).
enum DmButtonKind { dark, gold, outline }

class DmButton extends StatelessWidget {
  const DmButton(this.label, {super.key, required this.onPressed, this.kind = DmButtonKind.dark, this.icon});

  final String label;
  final VoidCallback? onPressed;
  final DmButtonKind kind;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final shape = RoundedRectangleBorder(borderRadius: BorderRadius.circular(DmRadius.card));
    const pad = EdgeInsets.symmetric(vertical: 14, horizontal: 18);
    final text = icon == null
        ? Text(label)
        : Row(mainAxisSize: MainAxisSize.min, children: [Icon(icon, size: 16), const SizedBox(width: 6), Text(label)]);
    switch (kind) {
      case DmButtonKind.dark:
        return FilledButton(onPressed: onPressed, child: text);
      case DmButtonKind.gold:
        return FilledButton(
          onPressed: onPressed,
          style: FilledButton.styleFrom(
              backgroundColor: DmColors.gold, foregroundColor: DmColors.inkDeep, shape: shape, padding: pad, textStyle: DmText.button),
          child: text,
        );
      case DmButtonKind.outline:
        return OutlinedButton(onPressed: onPressed, child: text);
    }
  }
}

/// Glass score badge used on photos ("IA 96%").
class DmScoreBadge extends StatelessWidget {
  const DmScoreBadge(this.label, {super.key});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(DmRadius.pill),
        border: Border.all(color: Colors.white.withValues(alpha: 0.2)),
      ),
      child: Text(label, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: Colors.white)),
    );
  }
}

/// "Pourquoi ... ?" block: a list of reasons with the gold diamond bullet.
class DmReasons extends StatelessWidget {
  const DmReasons(this.reasons, {super.key});

  final List<String> reasons;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final r in reasons)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('◆ ', style: TextStyle(fontSize: 12, color: DmColors.bar)),
              Expanded(child: Text(r, style: DmText.body)),
            ]),
          ),
      ],
    );
  }
}

/// Floating dark toast ("Tenue ajoutée à ton journal").
void dmToast(BuildContext context, String message) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(
        content: Text(message, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
        duration: const Duration(milliseconds: 2200)));
}

/// Friendly empty / error state: icon, title, one line, optional action.
class DmEmptyState extends StatelessWidget {
  const DmEmptyState({super.key, required this.title, required this.message, this.icon = Icons.checkroom_outlined, this.action});

  final String title;
  final String message;
  final IconData icon;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(28),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        Container(
          width: 56,
          height: 56,
          decoration: const BoxDecoration(color: DmColors.sandDark, shape: BoxShape.circle),
          child: Icon(icon, color: DmColors.bronzeDark),
        ),
        const SizedBox(height: 14),
        Text(title, style: DmText.cardTitle, textAlign: TextAlign.center),
        const SizedBox(height: 6),
        Text(message, style: DmText.body, textAlign: TextAlign.center),
        if (action != null) ...[const SizedBox(height: 16), action!],
      ]),
    );
  }
}
