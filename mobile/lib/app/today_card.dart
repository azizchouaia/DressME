// Home "Today": the outfit of the day from the user's own pieces (BO2 daily_plan -> M4 -> M2 on the M1
// wardrobe, ranked with the M5 taste), with ✓ I wear it (logs the wear: M4 -> M3), ↻ Another, See it on me.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api/dm_api.dart';
import '../core/design/dressme_design.dart';
import '../core/widgets/outfit_strip.dart';

class TodayCard extends ConsumerStatefulWidget {
  const TodayCard({super.key});

  @override
  ConsumerState<TodayCard> createState() => _TodayCardState();
}

class _TodayCardState extends ConsumerState<TodayCard> {
  Json? day;
  String? error;
  String? busy; // 'today' | 'change' | 'wear'
  bool worn = false;

  @override
  void initState() {
    super.initState();
    _run('today');
  }

  Future<void> _run(String action) async {
    setState(() {
      busy = action;
      error = null;
    });
    try {
      final r = await ref.read(dmApiProvider).post('/bo/chat', {
        'agent': 'daily_plan',
        'user_id': DemoUsers.wardrobe,
        'session_id': 'home-today',
        'message': '',
        'payload': {'action': action, 'args': <String, dynamic>{}, 'reply': false},
      });
      final res = ((r['result'] as Map?) ?? const {}).cast<String, dynamic>();
      final data = ((res['data'] as Map?) ?? const {}).cast<String, dynamic>();
      if (res['error'] != null) throw Exception('${res['error']}');
      setState(() {
        day = data;
        if (action == 'wear') worn = true;
        if (action == 'change') worn = false;
      });
    } catch (e) {
      setState(() => error = e is Exception ? '$e'.replaceFirst('Exception: ', '') : apiError(e));
    }
    if (mounted) setState(() => busy = null);
  }

  IconData _weatherIcon(Map? w) {
    final cond = '${w?['condition'] ?? ''}';
    final t = (w?['temp_c'] as num?) ?? 20;
    if (cond.contains('rain') || w?['rain'] == true) return Icons.water_drop_outlined;
    if (t >= 25) return Icons.wb_sunny_outlined;
    if (t < 12) return Icons.ac_unit;
    return Icons.cloud_outlined;
  }

  @override
  Widget build(BuildContext context) {
    final d = day;
    final ids = [for (final i in (d?['item_ids'] as List? ?? const [])) '$i'];
    final names = [for (final n in (d?['pieces'] as List? ?? const [])) '$n'];
    final w = d?['weather'] as Map?;
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        gradient: const LinearGradient(colors: [DmColors.inkDeep, Color(0xFF2A241D)], begin: Alignment.topLeft, end: Alignment.bottomRight),
        borderRadius: BorderRadius.circular(DmRadius.panel),
        boxShadow: const [BoxShadow(color: Color(0x33000000), blurRadius: 18, offset: Offset(0, 8))],
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Row(children: [
          const Text('TODAY', style: TextStyle(color: DmColors.gold, fontSize: 11, fontWeight: FontWeight.w700, letterSpacing: 2)),
          const Spacer(),
          if (w != null) ...[
            Icon(_weatherIcon(w), size: 16, color: DmColors.goldLight),
            const SizedBox(width: 4),
            Text('${(w['temp_c'] as num?)?.round() ?? '–'} °C', style: const TextStyle(color: DmColors.goldLight, fontSize: 13)),
            const SizedBox(width: 10),
          ],
          if (d?['occasion'] != null)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(color: Colors.white10, borderRadius: BorderRadius.circular(DmRadius.pill)),
              child: Text(cap('${d!['occasion']}'), style: const TextStyle(color: Colors.white, fontSize: 12)),
            ),
        ]),
        const SizedBox(height: 6),
        Text(worn ? 'Enjoy your day ✓' : 'Your outfit of the day',
            style: const TextStyle(color: Colors.white, fontFamily: DmFonts.serif, fontSize: 24)),
        const SizedBox(height: 12),
        if (busy == 'today' && d == null)
          const Padding(padding: EdgeInsets.all(18), child: Center(child: CircularProgressIndicator(color: DmColors.gold)))
        else if (error != null)
          Text(error!, style: const TextStyle(color: DmColors.goldLight))
        else if (ids.isEmpty)
          const Text('No outfit yet: add at least a top, a bottom and shoes in your wardrobe.',
              style: TextStyle(color: DmColors.goldLight))
        else
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(DmRadius.card)),
            child: AnimatedSwitcher(
              duration: const Duration(milliseconds: 300),
              child: OutfitStrip(key: ValueKey(ids.join(',')), ids: ids, names: names, size: 70),
            ),
          ),
        const SizedBox(height: 12),
        Row(children: [
          Expanded(
            child: FilledButton.icon(
              style: FilledButton.styleFrom(backgroundColor: DmColors.gold, foregroundColor: DmColors.inkDeep),
              onPressed: busy != null || ids.isEmpty || worn ? null : () => _run('wear'),
              icon: busy == 'wear'
                  ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                  : Icon(worn ? Icons.check_circle : Icons.check_rounded, size: 18),
              label: Text(worn ? 'Logged as worn' : 'I wear it'),
            ),
          ),
          const SizedBox(width: 10),
          OutlinedButton.icon(
            style: OutlinedButton.styleFrom(foregroundColor: Colors.white, side: const BorderSide(color: Colors.white38)),
            onPressed: busy != null || ids.isEmpty ? null : () => _run('change'),
            icon: busy == 'change'
                ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                : const Icon(Icons.refresh_rounded, size: 18),
            label: const Text('Another'),
          ),
        ]),
      ]),
    );
  }
}
