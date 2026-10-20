// Owner: BO7 · M15 — small widgets shared by the challenge screens.
import 'package:flutter/material.dart';

import '../data/challenge_models.dart';

Color hexColor(String hex) {
  final h = hex.replaceFirst('#', '');
  return Color(int.parse(h.length == 6 ? 'FF$h' : h, radix: 16));
}

IconData categoryIcon(String category) => switch (category) {
      'shoes' => Icons.directions_walk,
      'accessory' => Icons.shopping_bag_outlined,
      'traditional' => Icons.auto_awesome_outlined,
      _ => Icons.checkroom,
    };

/// One circle per day: green = valid, red = rule broken, outlined = not logged, ring = next day.
class DayStrip extends StatelessWidget {
  const DayStrip({super.key, required this.progress});
  final ChallengeProgress progress;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        for (var d = 1; d <= progress.durationDays; d++)
          Builder(builder: (context) {
            final s = progress.statusOfDay(d);
            final isNext = progress.nextDay == d;
            final bg = s == null ? Colors.transparent : (s ? Colors.green.shade600 : cs.error);
            final fg = s == null ? cs.onSurface : Colors.white;
            return Semantics(
              label: 'Day $d: ${s == null ? 'not logged' : s ? 'valid' : 'rule broken'}',
              child: Container(
                key: ValueKey('day-$d'),
                width: 38,
                height: 38,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: bg,
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: isNext ? cs.primary : cs.outlineVariant,
                    width: isNext ? 2.5 : 1,
                  ),
                ),
                child: s == null
                    ? Text('$d', style: TextStyle(color: fg))
                    : Icon(s ? Icons.check : Icons.close, size: 18, color: fg),
              ),
            );
          }),
      ],
    );
  }
}

/// How well the user's wardrobe fits the challenge (from the backend feasibility score).
class FeasibilityBar extends StatelessWidget {
  const FeasibilityBar({super.key, required this.value, this.reason});
  final double value;
  final String? reason;

  @override
  Widget build(BuildContext context) {
    final color = value >= 1
        ? Colors.green.shade600
        : value >= 0.6
            ? Colors.orange.shade700
            : Theme.of(context).colorScheme.error;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(children: [
          Text('Your wardrobe fit', style: Theme.of(context).textTheme.labelMedium),
          const Spacer(),
          Text('${(value * 100).round()}%', style: TextStyle(color: color, fontWeight: FontWeight.w600)),
        ]),
        const SizedBox(height: 4),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(value: value.clamp(0, 1), minHeight: 6, color: color),
        ),
        if (reason != null) ...[
          const SizedBox(height: 4),
          Text(reason!, style: Theme.of(context).textTheme.bodySmall),
        ],
      ],
    );
  }
}

class GarmentChip extends StatelessWidget {
  const GarmentChip({super.key, required this.item, this.selected = false, this.onTap});
  final WardrobeItem item;
  final bool selected;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final c = hexColor(item.colorHex);
    final dark = c.computeLuminance() < 0.4;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        width: 104,
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: c,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: selected ? Theme.of(context).colorScheme.primary : Colors.black12,
            width: selected ? 3 : 1,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Icon(categoryIcon(item.category), color: dark ? Colors.white : Colors.black87),
              const Spacer(),
              if (selected) Icon(Icons.check_circle, color: dark ? Colors.white : Colors.black87, size: 18),
            ]),
            const SizedBox(height: 18),
            Text(
              item.name,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(color: dark ? Colors.white : Colors.black87, fontWeight: FontWeight.w600),
            ),
            if (item.localBrand != null)
              Text(item.localBrand!,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(fontSize: 11, color: dark ? Colors.white70 : Colors.black54)),
          ],
        ),
      ),
    );
  }
}
