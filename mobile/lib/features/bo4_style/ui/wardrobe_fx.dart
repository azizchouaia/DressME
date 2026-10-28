// Owner: BO4 (Amine) — the closet animations of Amine's web UI (modules/m01_wardrobe/ui/styles.css):
// two doors that open in 3D, pieces that fade up one by one, hanging pieces that swing, flat pieces that
// lift, a new piece that drops into place.
import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../../core/design/dressme_design.dart';

const _ease = Cubic(0.22, 1, 0.36, 1); // --ease-out of Amine's CSS

/// The closed wardrobe: two wooden doors and an "Open" button. The doors turn 100° (rotateY) and the
/// content is revealed. [open] can be driven from outside (e.g. after adding a piece).
class WardrobeDoors extends StatefulWidget {
  const WardrobeDoors({super.key, required this.child, this.onOpened});

  final Widget child;
  final VoidCallback? onOpened;

  @override
  State<WardrobeDoors> createState() => WardrobeDoorsState();
}

class WardrobeDoorsState extends State<WardrobeDoors> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 900));
  late final Animation<double> _t = CurvedAnimation(parent: _c, curve: _ease);

  bool get isOpen => _c.status == AnimationStatus.completed;

  void open() {
    if (_c.status == AnimationStatus.completed || _c.status == AnimationStatus.forward) return;
    _c.forward().then((_) => widget.onOpened?.call());
  }

  void close() => _c.reverse();

  @override
  void initState() {
    super.initState();
    _c.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  Widget _door({required bool left}) {
    final angle = (left ? -1 : 1) * _t.value * 100 * math.pi / 180;
    return Expanded(
      child: Transform(
        alignment: left ? Alignment.centerLeft : Alignment.centerRight,
        transform: Matrix4.identity()
          ..setEntry(3, 2, 0.0012) // perspective
          ..rotateY(angle),
        child: Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: left ? Alignment.centerLeft : Alignment.centerRight,
              end: left ? Alignment.centerRight : Alignment.centerLeft,
              colors: const [Color(0xFFB98F63), Color(0xFF9C7550)],
            ),
            border: Border(
              left: left ? BorderSide.none : const BorderSide(color: Color(0x33FFFFFF)),
              right: left ? const BorderSide(color: Color(0x596E5032)) : BorderSide.none,
            ),
          ),
          child: Stack(children: [
            // the inset panels of the door
            Positioned.fill(
              child: Padding(
                padding: const EdgeInsets.all(18),
                child: Column(children: [
                  Expanded(flex: 3, child: _panel()),
                  const SizedBox(height: 14),
                  Expanded(flex: 2, child: _panel()),
                ]),
              ),
            ),
            // the knob, near the middle of the wardrobe
            Align(
              alignment: left ? const Alignment(0.86, 0) : const Alignment(-0.86, 0),
              child: Container(
                width: 10,
                height: 110,
                decoration: BoxDecoration(
                  color: const Color(0xFFE7D2B0),
                  borderRadius: BorderRadius.circular(6),
                  boxShadow: const [BoxShadow(color: Color(0x40000000), blurRadius: 4, offset: Offset(1, 2))],
                ),
              ),
            ),
          ]),
        ),
      ),
    );
  }

  Widget _panel() => Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: const Color(0x406E5032), width: 1.5),
        ),
      );

  @override
  Widget build(BuildContext context) {
    final closed = _c.status == AnimationStatus.dismissed;
    final done = _c.status == AnimationStatus.completed;
    return ClipRRect(
      borderRadius: BorderRadius.circular(DmRadius.panel),
      child: Stack(children: [
        // content: hidden while closed, fades in as the doors open
        ConstrainedBox(
          constraints: const BoxConstraints(minHeight: 420),
          child: Opacity(opacity: closed ? 0 : _t.value.clamp(0.0, 1.0), child: widget.child),
        ),
        if (!done)
          Positioned.fill(
            child: IgnorePointer(
              ignoring: !closed,
              child: GestureDetector(
                onTap: open,
                child: Row(children: [_door(left: true), _door(left: false)]),
              ),
            ),
          ),
        if (closed)
          Positioned.fill(
            child: Center(
              child: FilledButton.icon(
                style: FilledButton.styleFrom(
                  backgroundColor: DmColors.page,
                  foregroundColor: DmColors.ink,
                  padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 14),
                  shape: const StadiumBorder(),
                ),
                onPressed: open,
                icon: const Icon(Icons.door_sliding_outlined),
                label: const Text('Open the wardrobe'),
              ),
            ),
          ),
        if (done)
          Positioned(
            top: 6,
            right: 6,
            child: IconButton(
              tooltip: 'Close the wardrobe',
              onPressed: close,
              icon: const Icon(Icons.close_fullscreen_rounded, size: 18, color: DmColors.bronze),
            ),
          ),
      ]),
    );
  }
}

/// fade-up .55s with a delay of 340 ms + i × 35 ms (the reveal after the doors open).
class FadeUp extends StatefulWidget {
  const FadeUp({super.key, required this.index, required this.child, this.baseDelayMs = 340});

  final int index;
  final int baseDelayMs;
  final Widget child;

  @override
  State<FadeUp> createState() => _FadeUpState();
}

class _FadeUpState extends State<FadeUp> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 550));

  @override
  void initState() {
    super.initState();
    Future.delayed(Duration(milliseconds: widget.baseDelayMs + widget.index * 35), () {
      if (mounted) _c.forward();
    });
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
          final t = _ease.transform(_c.value);
          return Opacity(opacity: t, child: Transform.translate(offset: Offset(0, 14 * (1 - t)), child: child));
        },
        child: widget.child,
      );
}

/// drop-in .9s: a new piece falls into its place with a small bounce.
class DropIn extends StatefulWidget {
  const DropIn({super.key, required this.child});

  final Widget child;

  @override
  State<DropIn> createState() => _DropInState();
}

class _DropInState extends State<DropIn> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 900))..forward();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
        animation: _c,
        builder: (_, child) {
          final t = Curves.easeOutBack.transform(_c.value);
          return Opacity(
            opacity: _c.value.clamp(0.0, 1.0),
            child: Transform.translate(offset: Offset(0, -60 * (1 - t)), child: Transform.scale(scale: 0.9 + 0.1 * t, child: child)),
          );
        },
        child: widget.child,
      );
}

/// A hanging piece: swings from its hanger when the pointer comes over it (swing 1.8s).
class Swing extends StatefulWidget {
  const Swing({super.key, required this.child});

  final Widget child;

  @override
  State<Swing> createState() => _SwingState();
}

class _SwingState extends State<Swing> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1800));

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => MouseRegion(
        onEnter: (_) => _c.forward(from: 0),
        child: GestureDetector(
          behavior: HitTestBehavior.translucent,
          onLongPressStart: (_) => _c.forward(from: 0), // touch screens
          child: AnimatedBuilder(
            animation: _c,
            builder: (_, child) {
              final t = _c.value;
              final angle = math.sin(t * math.pi * 4) * (1 - t) * 6 * math.pi / 180; // damped ±6°
              return Transform.rotate(angle: angle, alignment: Alignment.topCenter, child: child);
            },
            child: widget.child,
          ),
        ),
      );
}

/// A flat piece on a shelf: lifts 3 px with a soft shadow on hover; [slanted] tilts it like Amine's shoe shelves.
class HoverLift extends StatefulWidget {
  const HoverLift({super.key, required this.child, this.slanted = false});

  final Widget child;
  final bool slanted;

  @override
  State<HoverLift> createState() => _HoverLiftState();
}

class _HoverLiftState extends State<HoverLift> {
  bool hover = false;

  @override
  Widget build(BuildContext context) => MouseRegion(
        onEnter: (_) => setState(() => hover = true),
        onExit: (_) => setState(() => hover = false),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 350),
          curve: _ease,
          transformAlignment: Alignment.bottomCenter,
          transform: Matrix4.translationValues(0, hover ? -3 : 0, 0)
            ..rotateZ(widget.slanted ? -8 * math.pi / 180 : 0),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(DmRadius.card),
            boxShadow: [if (hover) const BoxShadow(color: Color(0x42211D19), blurRadius: 14, offset: Offset(0, 10))],
          ),
          child: widget.child,
        ),
      );
}
