// First-launch tour: 4 slides that show what DressMe does, once per device (shared_preferences).
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../core/design/dressme_design.dart';
import '../core/widgets/dm_motion.dart';

const _key = 'dressme_tour_v1';

const _slides = [
  (Icons.photo_camera_outlined, 'Your closet, digitised', 'One photo per piece: it is cut out, classified and hung in your wardrobe.', '/bo4_style', 'Add my first piece'),
  (Icons.style_outlined, 'It learns your style', 'Swipe 10 looks: right if you like, left if not. No form to fill in.', '/my_style', 'Swipe now'),
  (Icons.view_in_ar_outlined, 'See it on you', 'Every outfit opens on your 3D avatar. Share the looks you love.', '/bo9_avatar', 'Build my avatar'),
  (Icons.mic_none_rounded, 'Just ask', 'Write, speak or send a photo: "should I buy it?", "what do I wear tomorrow?"', '/bo8_assistant', 'Ask something'),
];

Future<void> showTourIfNeeded(BuildContext context) async {
  try {
    final prefs = await SharedPreferences.getInstance();
    if (prefs.getBool(_key) == true) return;
    await prefs.setBool(_key, true);
    if (!context.mounted) return;
    await showGeneralDialog<void>(
      context: context,
      barrierDismissible: false,
      barrierColor: Colors.black54,
      transitionDuration: const Duration(milliseconds: 350),
      transitionBuilder: (_, a, __, child) => FadeTransition(
        opacity: a,
        child: ScaleTransition(scale: Tween(begin: .94, end: 1.0).animate(CurvedAnimation(parent: a, curve: dmEase)), child: child),
      ),
      pageBuilder: (dialogContext, _, __) => _Tour(onGo: (route) {
        Navigator.of(dialogContext).pop();
        if (route != null && context.mounted) context.go(route);
      }),
    );
  } catch (_) {
    // no storage (private window): no tour, the app still works
  }
}

class _Tour extends StatefulWidget {
  const _Tour({required this.onGo});

  final void Function(String? route) onGo;

  @override
  State<_Tour> createState() => _TourState();
}

class _TourState extends State<_Tour> {
  final _pages = PageController();
  int page = 0;

  @override
  void dispose() {
    _pages.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final last = page == _slides.length - 1;
    return Center(
      child: Material(
        color: Colors.transparent,
        child: Container(
          width: 420,
          height: 520,
          margin: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            gradient: const LinearGradient(colors: [DmColors.inkDeep, Color(0xFF2A241D)], begin: Alignment.topLeft, end: Alignment.bottomRight),
            borderRadius: BorderRadius.circular(DmRadius.hero),
            boxShadow: const [BoxShadow(color: Color(0x66000000), blurRadius: 40, offset: Offset(0, 20))],
          ),
          child: Column(children: [
            Align(
              alignment: Alignment.topRight,
              child: TextButton(
                onPressed: () => widget.onGo(null),
                child: const Text('Skip', style: TextStyle(color: DmColors.goldLight)),
              ),
            ),
            Expanded(
              child: PageView(
                controller: _pages,
                onPageChanged: (i) => setState(() => page = i),
                children: [
                  for (final (i, s) in _slides.indexed)
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 28),
                      child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                        DmFloat(
                          child: Container(
                            width: 96,
                            height: 96,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              gradient: const LinearGradient(colors: [DmColors.goldLight, DmColors.gold]),
                              boxShadow: [BoxShadow(color: DmColors.gold.withValues(alpha: .45), blurRadius: 30)],
                            ),
                            child: Icon(s.$1, size: 44, color: DmColors.inkDeep),
                          ),
                        ),
                        const SizedBox(height: 28),
                        Text('${i + 1} / ${_slides.length}',
                            style: const TextStyle(color: DmColors.gold, fontSize: 12, fontWeight: FontWeight.w700, letterSpacing: 2)),
                        const SizedBox(height: 8),
                        Text(s.$2,
                            textAlign: TextAlign.center,
                            style: const TextStyle(color: Colors.white, fontFamily: DmFonts.serif, fontSize: 28, height: 1.1)),
                        const SizedBox(height: 12),
                        Text(s.$3, textAlign: TextAlign.center, style: const TextStyle(color: DmColors.goldLight, fontSize: 15, height: 1.4)),
                        const SizedBox(height: 18),
                        TextButton.icon(
                          onPressed: () => widget.onGo(s.$4),
                          icon: const Icon(Icons.arrow_forward_rounded, size: 16, color: Colors.white70),
                          label: Text(s.$5, style: const TextStyle(color: Colors.white70)),
                        ),
                      ]),
                    ),
                ],
              ),
            ),
            Row(mainAxisAlignment: MainAxisAlignment.center, children: [
              for (var i = 0; i < _slides.length; i++)
                AnimatedContainer(
                  duration: const Duration(milliseconds: 250),
                  margin: const EdgeInsets.symmetric(horizontal: 3),
                  width: i == page ? 22 : 7,
                  height: 7,
                  decoration: BoxDecoration(color: i == page ? DmColors.gold : Colors.white24, borderRadius: BorderRadius.circular(4)),
                ),
            ]),
            Padding(
              padding: const EdgeInsets.all(20),
              child: SizedBox(
                width: double.infinity,
                height: 50,
                child: FilledButton(
                  style: FilledButton.styleFrom(backgroundColor: DmColors.gold, foregroundColor: DmColors.inkDeep),
                  onPressed: () => last
                      ? widget.onGo(null)
                      : _pages.nextPage(duration: const Duration(milliseconds: 380), curve: dmEase),
                  child: Text(last ? "Let's start" : 'Next'),
                ),
              ),
            ),
          ]),
        ),
      ),
    );
  }
}
