// Small shared pieces for the BO screens: page frame, loading / error states, source badge.
import 'package:flutter/material.dart';

import '../api/dm_api.dart';
import '../design/dressme_design.dart';
import 'dm_widgets.dart';
import 'dm_motion.dart';

/// Standard BO page: dark hero on top, centred content (max 620 px) below.
class DmPage extends StatelessWidget {
  const DmPage({super.key, required this.eyebrow, required this.title, required this.children, this.heroChild, this.trailing});

  final String eyebrow;
  final String title;
  final List<Widget> children;
  final Widget? heroChild;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: ListView(padding: EdgeInsets.zero, children: [
        DmHero(eyebrow: eyebrow, title: title, trailing: trailing, child: heroChild),
        Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 620),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 20, 16, 40),
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: children),
            ),
          ),
        ),
      ]),
    );
  }
}

/// Runs [load] and shows a spinner, a clear error with "Try again", or [builder]'s widget.
class DmLoad extends StatefulWidget {
  const DmLoad({super.key, required this.load, required this.builder});

  final Future<Json> Function() load;
  final Widget Function(Json data, VoidCallback reload) builder;

  @override
  State<DmLoad> createState() => _DmLoadState();
}

class _DmLoadState extends State<DmLoad> {
  late Future<Json> _future = widget.load();

  void _reload() => setState(() => _future = widget.load());

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Json>(
      future: _future,
      builder: (context, snap) {
        final Widget body;
        if (snap.connectionState != ConnectionState.done) {
          body = const DmSkeleton(key: ValueKey('loading')); // the shape of what comes, not a spinner
        } else if (snap.hasError) {
          body = DmError(apiError(snap.error!), onRetry: _reload);
        } else {
          body = KeyedSubtree(key: const ValueKey('data'), child: widget.builder(snap.data!, _reload));
        }
        return AnimatedSwitcher(
          duration: const Duration(milliseconds: 280),
          switchInCurve: dmEase,
          layoutBuilder: (current, previous) => Stack(alignment: Alignment.topCenter, children: [...previous, if (current != null) current]),
          child: body,
        );
      },
    );
  }
}

class DmError extends StatelessWidget {
  const DmError(this.message, {super.key, this.onRetry});

  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return DmCard(
      child: DmEmptyState(
        icon: Icons.wifi_off_rounded,
        title: 'Something went wrong',
        message: message,
        action: onRetry == null ? null : DmButton('Try again', onPressed: onRetry),
      ),
    );
  }
}

/// "real" / "mock" badge, so the tester sees which modules are really connected.
class DmSource extends StatelessWidget {
  const DmSource({super.key, required this.mocked, this.label});

  final bool mocked;
  final String? label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: mocked ? DmColors.warningBg : DmColors.successBg,
        borderRadius: BorderRadius.circular(DmRadius.pill),
      ),
      child: Text(
        '${label ?? ''}${label == null ? '' : ' · '}${mocked ? 'mock' : 'real'}',
        style: DmText.caption.copyWith(color: mocked ? DmColors.warning : DmColors.successDark, fontWeight: FontWeight.w700),
      ),
    );
  }
}

/// A wardrobe piece as a small tile: picture if any, else an icon + its name.
class DmPieceTile extends StatelessWidget {
  const DmPieceTile({super.key, required this.name, this.imageUrl, this.caption, this.width = 110});

  final String name;
  final String? imageUrl;
  final String? caption;
  final double width;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: width,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(DmRadius.small),
          child: Container(
            height: width,
            width: width,
            color: DmColors.sand,
            child: imageUrl == null || imageUrl!.isEmpty
                ? const Icon(Icons.checkroom, color: DmColors.bronze)
                : Image.network(imageUrl!, fit: BoxFit.contain,
                    errorBuilder: (_, __, ___) => const Icon(Icons.checkroom, color: DmColors.bronze)),
          ),
        ),
        const SizedBox(height: 4),
        Text(cap(name), style: DmText.itemName, maxLines: 2, overflow: TextOverflow.ellipsis),
        if (caption != null) Text(caption!, style: DmText.caption, maxLines: 1, overflow: TextOverflow.ellipsis),
      ]),
    );
  }
}
