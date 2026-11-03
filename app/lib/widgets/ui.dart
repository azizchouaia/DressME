import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../config.dart';
import '../garments.dart';
import '../models.dart';
import '../theme.dart';

class PageFrame extends StatelessWidget {
  const PageFrame({super.key, required this.child, this.padding = const EdgeInsets.fromLTRB(20, 8, 20, 24)});

  final Widget child;
  final EdgeInsets padding;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.topCenter,
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 720),
        child: Padding(padding: padding, child: child),
      ),
    );
  }
}

class PageHeader extends StatelessWidget {
  const PageHeader({super.key, required this.title, this.subtitle, this.action, this.showBack = false});

  final String title;
  final String? subtitle;
  final Widget? action;
  final bool showBack;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (showBack)
            Padding(
              padding: const EdgeInsets.only(right: 4),
              child: IconButton(
                onPressed: () {
                  if (context.canPop()) {
                    context.pop();
                  } else {
                    context.go('/home');
                  }
                },
                icon: const Icon(Icons.arrow_back),
                tooltip: 'Back',
              ),
            ),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(fontFamily: 'Georgia', fontSize: 32, height: 1.05, fontWeight: FontWeight.w500)),
                if (subtitle != null) ...[
                  const SizedBox(height: 6),
                  Text(subtitle!, style: const TextStyle(color: muted)),
                ],
              ],
            ),
          ),
          ?action,
        ],
      ),
    );
  }
}

class PrimaryButton extends StatelessWidget {
  const PrimaryButton({super.key, required this.label, required this.onPressed, this.busy = false, this.icon});

  final String label;
  final VoidCallback? onPressed;
  final bool busy;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    return FilledButton(
      onPressed: busy ? null : onPressed,
      child: busy
          ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: paper))
          : Row(
              mainAxisAlignment: MainAxisAlignment.center,
              mainAxisSize: MainAxisSize.min,
              children: [
                if (icon != null) ...[Icon(icon, size: 18), const SizedBox(width: 8)],
                Text(label),
              ],
            ),
    );
  }
}

class SecondaryButton extends StatelessWidget {
  const SecondaryButton({super.key, required this.label, required this.onPressed, this.busy = false, this.icon});

  final String label;
  final VoidCallback? onPressed;
  final bool busy;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    return OutlinedButton(
      onPressed: busy ? null : onPressed,
      child: busy
          ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
          : Row(
              mainAxisAlignment: MainAxisAlignment.center,
              mainAxisSize: MainAxisSize.min,
              children: [
                if (icon != null) ...[Icon(icon, size: 18), const SizedBox(width: 8)],
                Text(label),
              ],
            ),
    );
  }
}

class ChoiceChips extends StatelessWidget {
  const ChoiceChips({super.key, required this.options, required this.value, required this.onChanged});

  final List<(String, String)> options;
  final String value;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 42,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: options.length,
        separatorBuilder: (_, _) => const SizedBox(width: 8),
        itemBuilder: (context, index) {
          final (id, label) = options[index];
          final selected = id == value;
          return ChoiceChip(
            label: Text(label),
            selected: selected,
            onSelected: (_) => onChanged(id),
            selectedColor: ink,
            labelStyle: TextStyle(color: selected ? paper : ink),
            backgroundColor: surface,
            side: const BorderSide(color: line),
            showCheckmark: false,
          );
        },
      ),
    );
  }
}

class StatusMessage extends StatelessWidget {
  const StatusMessage({super.key, required this.message, this.onRetry});

  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 24),
      child: Column(
        children: [
          Text(message, textAlign: TextAlign.center, style: const TextStyle(color: inkSoft)),
          if (onRetry != null) ...[
            const SizedBox(height: 12),
            SecondaryButton(label: 'Try again', onPressed: onRetry),
          ],
        ],
      ),
    );
  }
}

class EmptyPanel extends StatelessWidget {
  const EmptyPanel({super.key, required this.title, required this.text, this.action});

  final String title;
  final String text;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 32),
      child: Column(
        children: [
          Text(title, style: const TextStyle(fontFamily: 'Georgia', fontSize: 24)),
          const SizedBox(height: 8),
          Text(text, textAlign: TextAlign.center, style: const TextStyle(color: muted)),
          if (action != null) ...[const SizedBox(height: 16), action!],
        ],
      ),
    );
  }
}

class ClothingThumb extends StatelessWidget {
  const ClothingThumb({super.key, required this.item, this.size = 96});

  final ClothingItem item;
  final double? size;

  @override
  Widget build(BuildContext context) {
    final source = item.thumbnailUrl ?? item.imageUrl;
    final swatch = Color(swatchFor(item.color));
    final image = source == null
        ? _Fallback(item: item, swatch: swatch)
        : Image.network(
            resolveUrl(source),
            fit: BoxFit.cover,
            width: double.infinity,
            height: double.infinity,
            errorBuilder: (_, _, _) => _Fallback(item: item, swatch: swatch),
          );
    final framed = ClipRRect(
      borderRadius: BorderRadius.circular(16),
      child: ColoredBox(color: const Color(0xFFEFEBE4), child: image),
    );
    if (size == null) return AspectRatio(aspectRatio: 1, child: framed);
    return SizedBox(width: size, height: size, child: framed);
  }
}

class _Fallback extends StatelessWidget {
  const _Fallback({required this.item, required this.swatch});

  final ClothingItem item;
  final Color swatch;

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: swatch,
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(8),
          child: Text(
            categoryLabels[item.category] ?? item.category,
            textAlign: TextAlign.center,
            style: TextStyle(
              color: swatch.computeLuminance() > 0.6 ? ink : Colors.white,
              fontWeight: FontWeight.w600,
              fontSize: 12,
            ),
          ),
        ),
      ),
    );
  }
}

class AppCard extends StatelessWidget {
  const AppCard({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(padding: const EdgeInsets.all(16), child: child),
    );
  }
}
