// Owner: BO2 (Racem) — save time: outfit of the day (M4), the week, a capsule (M17). Integration screen.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/dm_api.dart';
import '../../../core/design/dressme_design.dart';
import '../../../core/widgets/dm_async.dart';
import '../../../core/widgets/dm_widgets.dart';

class OutfitOfDayScreen extends ConsumerStatefulWidget {
  const OutfitOfDayScreen({super.key});

  @override
  ConsumerState<OutfitOfDayScreen> createState() => _OutfitOfDayScreenState();
}

class _OutfitOfDayScreenState extends ConsumerState<OutfitOfDayScreen> {
  int _tab = 0; // 0 today, 1 week, 2 capsule
  int _run = 0;
  bool _tomorrow = false;

  DmApi get _api => ref.read(dmApiProvider);

  Future<void> _act(String path, String done) async {
    try {
      await _api.call(path, userId: DemoUsers.outfits, payload: {'kind': _tomorrow ? 'tomorrow' : 'day'});
      if (mounted) {
        dmToast(context, done);
        setState(() => _run++);
      }
    } catch (e) {
      if (mounted) dmToast(context, apiError(e));
    }
  }

  @override
  Widget build(BuildContext context) {
    return DmPage(
      eyebrow: 'BO2 · Save time every morning',
      title: 'Ready in one tap',
      heroChild: Wrap(spacing: 6, children: [
        for (final (i, label) in const [(0, 'Today'), (1, 'Week'), (2, 'Capsule')])
          DmChoiceChip(label: label, selected: _tab == i, onDark: true, onTap: () => setState(() => _tab = i)),
      ]),
      children: [
        if (_tab == 0) ...[
          Row(children: [
            DmChoiceChip(label: 'Today', selected: !_tomorrow, onTap: () => setState(() => _tomorrow = false)),
            const SizedBox(width: 6),
            DmChoiceChip(label: 'Tomorrow', selected: _tomorrow, onTap: () => setState(() => _tomorrow = true)),
          ]),
          const SizedBox(height: 12),
          DmLoad(
            key: ValueKey('day-$_run-$_tomorrow'),
            load: () => _api.call(_tomorrow ? '/m04/tomorrow' : '/m04/today', userId: DemoUsers.outfits),
            builder: (d, _) => _DayCard(
              day: d,
              onApprove: () => _act('/m04/approve', 'Approved: it is ready for you'),
              onChange: () => _act('/m04/change', 'Here is another option'),
              onWear: () => _act('/m04/wear', 'Logged as worn (M3)'),
            ),
          ),
        ],
        if (_tab == 1)
          DmLoad(
            key: ValueKey('week-$_run'),
            load: () => _api.call('/m04/week', userId: DemoUsers.outfits, payload: {'days': 7}),
            builder: (d, _) => Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Row(children: [
                const Expanded(child: Text('Your week', style: DmText.cardTitle)),
                DmSource(mocked: d['_mocked'] == true, label: 'M4'),
              ]),
              const SizedBox(height: 10),
              for (final day in jsonList(d['days']))
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: DmCard(
                    child: Row(children: [
                      SizedBox(
                        width: 86,
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text('${day['date']}', style: DmText.caption),
                          Text(cap('${day['occasion'] ?? ''}'), style: DmText.cardTitle),
                        ]),
                      ),
                      Expanded(child: Text('${day['summary'] ?? ''}', style: DmText.body)),
                      if ((day['weather'] as Map?) != null) DmPill('${(day['weather'] as Map)['temp_c']}°'),
                    ]),
                  ),
                ),
            ]),
          ),
        if (_tab == 2)
          DmLoad(
            key: ValueKey('capsule-$_run'),
            load: () => _api.call('/m17/capsule', userId: DemoUsers.outfits),
            builder: (d, _) => _Capsule(data: d),
          ),
      ],
    );
  }
}

class _DayCard extends ConsumerWidget {
  const _DayCard({required this.day, required this.onApprove, required this.onChange, required this.onWear});

  final Json day;
  final VoidCallback onApprove;
  final VoidCallback onChange;
  final VoidCallback onWear;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final outfit = (day['outfit'] as Map?)?.cast<String, dynamic>() ?? const {};
    final items = (day['items'] as Map? ?? const {}).cast<String, dynamic>();
    final weather = day['weather'] as Map?;
    return DmCard(
      big: true,
      padding: const EdgeInsets.all(18),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(child: Text('${day['date']} · ${cap('${day['occasion'] ?? ''}')}', style: DmText.eyebrow)),
          DmSource(mocked: day['_mocked'] == true, label: 'M4'),
        ]),
        const SizedBox(height: 6),
        Text('${day['summary'] ?? ''}', style: DmText.title.copyWith(fontSize: 22)),
        if (weather != null) Text('${weather['temp_c']}°C · ${weather['condition']}', style: DmText.body),
        const SizedBox(height: 12),
        SizedBox(
          height: 150,
          child: ListView(scrollDirection: Axis.horizontal, children: [
            for (final id in (outfit['items'] as List? ?? const []))
              Padding(
                padding: const EdgeInsets.only(right: 10),
                child: DmPieceTile(
                  name: '${(items['$id'] as Map?)?['name'] ?? id}',
                  imageUrl: ref.read(dmApiProvider).media((items['$id'] as Map?)?['image'] as String?),
                  width: 100,
                ),
              ),
          ]),
        ),
        Text('${outfit['explanation'] ?? ''}', style: DmText.body),
        const SizedBox(height: 6),
        Text(day['approved'] == true ? '✓ Approved' : 'Option ${(day['choice'] ?? 0) + 1} of ${day['options'] ?? 1}',
            style: DmText.caption),
        const SizedBox(height: 12),
        Row(children: [
          Expanded(child: DmButton('Approve', kind: DmButtonKind.gold, onPressed: onApprove)),
          const SizedBox(width: 8),
          Expanded(child: DmButton('Another', kind: DmButtonKind.outline, onPressed: onChange)),
        ]),
        const SizedBox(height: 8),
        DmButton('I wore it', icon: Icons.check_rounded, onPressed: onWear),
      ]),
    );
  }
}

class _Capsule extends ConsumerWidget {
  const _Capsule({required this.data});

  final Json data;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final pieces = jsonList(data['pieces']);
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      DmCard(
        big: true,
        padding: const EdgeInsets.all(18),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            const Expanded(child: Text('Your capsule', style: DmText.title)),
            DmSource(mocked: data['_mocked'] == true, label: 'M17'),
          ]),
          const SizedBox(height: 6),
          Text('${pieces.length} pieces → ${data['n_outfits'] ?? '?'} outfits · ${data['season'] ?? ''}', style: DmText.body),
          const SizedBox(height: 4),
          Text('Method: ${data['method'] ?? ''}', style: DmText.caption),
        ]),
      ),
      const SizedBox(height: 12),
      Wrap(spacing: 10, runSpacing: 12, children: [
        for (final p in pieces)
          DmPieceTile(
            name: '${p['name'] ?? p['item_id']}',
            imageUrl: ref.read(dmApiProvider).media(p['image'] as String?),
            caption: '${p['outfits'] ?? 0} outfits',
            width: 100,
          ),
      ]),
    ]);
  }
}
