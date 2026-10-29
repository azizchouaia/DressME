// Motion kit shared by every screen: appear (fade + rise, staggered), press (scale), skeleton shimmer,
// floating icon. Short, soft curves so the app feels alive without slowing anyone down.
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../design/dressme_design.dart';

const dmEase = Cubic(0.22, 1, 0.36, 1);

/// Fades and rises its child the first time it is built. [index] staggers items of a list (40 ms each).
class DmAppear extends StatefulWidget {
  const DmAppear({super.key, required this.child, this.index = 0, this.offset = 14});

  final Widget child;
  final int index;
  final double offset;

  @override
  State<DmAppear> createState() => _DmAppearState();
}

class _DmAppearState extends State<DmAppear> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 420));

  @override
  void initState() {
    super.initState();
    final delay = Duration(milliseconds: (widget.index.clamp(0, 12)) * 40);
    if (delay == Duration.zero) {
      _c.forward();
    } else {
      Future.delayed(delay, () {
        if (mounted) _c.forward();
      });
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
        animation: _c,
        builder: (_, child) {
          final t = dmEase.transform(_c.value);
          return Opacity(opacity: t, child: Transform.translate(offset: Offset(0, widget.offset * (1 - t)), child: child));
        },
        child: widget.child,
      );
}

/// Shrinks a little under the finger, with a light haptic tick.
class DmPressable extends StatefulWidget {
  const DmPressable({super.key, required this.child, this.onTap, this.scale = .97});

  final Widget child;
  final VoidCallback? onTap;
  final double scale;

  @override
  State<DmPressable> createState() => _DmPressableState();
}

class _DmPressableState extends State<DmPressable> {
  bool _down = false;

  void _set(bool v) {
    if (widget.onTap != null && _down != v) setState(() => _down = v);
  }

  @override
  Widget build(BuildContext context) => Listener(
        onPointerDown: (_) => _set(true),
        onPointerUp: (_) => _set(false),
        onPointerCancel: (_) => _set(false),
        child: AnimatedScale(
          scale: _down ? widget.scale : 1,
          duration: const Duration(milliseconds: 120),
          curve: Curves.easeOut,
          child: widget.child,
        ),
      );
}

/// Light haptic feedback, then the action (no-op on the web).
VoidCallback? withHaptic(VoidCallback? f) => f == null
    ? null
    : () {
        HapticFeedback.lightImpact();
        f();
      };

/// A grey block with a moving light: the shape of what is loading.
class DmShimmer extends StatefulWidget {
  const DmShimmer({super.key, this.height = 16, this.width, this.radius = 10});

  final double height;
  final double? width;
  final double radius;

  @override
  State<DmShimmer> createState() => _DmShimmerState();
}

class _DmShimmerState extends State<DmShimmer> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1200))..repeat();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
        animation: _c,
        builder: (_, __) => Container(
          height: widget.height,
          width: widget.width,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(widget.radius),
            gradient: LinearGradient(
              begin: Alignment(-1.5 + 3 * _c.value, 0),
              end: Alignment(-0.5 + 3 * _c.value, 0),
              colors: const [DmColors.sand, DmColors.border, DmColors.sand],
            ),
          ),
        ),
      );
}

/// Skeleton of a loading section: a big card and two lines of cards.
class DmSkeleton extends StatelessWidget {
  const DmSkeleton({super.key, this.cards = 3});

  final int cards;

  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        for (var i = 0; i < cards; i++)
          Container(
            margin: const EdgeInsets.only(bottom: 10),
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: DmColors.surface,
              borderRadius: BorderRadius.circular(DmRadius.card),
              border: Border.all(color: DmColors.border),
            ),
            child: Row(children: [
              const DmShimmer(height: 44, width: 44, radius: 22),
              const SizedBox(width: 12),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  DmShimmer(height: 14, width: i.isEven ? 180 : 140),
                  const SizedBox(height: 8),
                  const DmShimmer(height: 10),
                ]),
              ),
            ]),
          ),
      ]);
}

/// An icon that floats gently (empty states).
class DmFloat extends StatefulWidget {
  const DmFloat({super.key, required this.child});

  final Widget child;

  @override
  State<DmFloat> createState() => _DmFloatState();
}

class _DmFloatState extends State<DmFloat> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 2400))..repeat(reverse: true);

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
        animation: _c,
        builder: (_, child) => Transform.translate(offset: Offset(0, -5 * Curves.easeInOut.transform(_c.value)), child: child),
        child: widget.child,
      );
}
