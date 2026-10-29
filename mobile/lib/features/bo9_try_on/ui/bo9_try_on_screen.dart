// Owner: BO9 — try it on: a faceless 3D avatar with your measurements wearing your pieces (M9). Integration screen.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/api/dm_api.dart';
import '../../../core/design/dressme_design.dart';
import '../../../core/widgets/dm_async.dart';
import '../../../core/widgets/dm_widgets.dart';

class TryOnScreen extends ConsumerStatefulWidget {
  const TryOnScreen({super.key});

  @override
  ConsumerState<TryOnScreen> createState() => _TryOnScreenState();
}

class _TryOnScreenState extends ConsumerState<TryOnScreen> {
  String _sex = 'female';
  double _height = 165;
  double _weight = 60;
  final _picked = <String>{};
  Json? _render;
  bool _busy = false;

  DmApi get _api => ref.read(dmApiProvider);

  Future<void> _go() async {
    setState(() => _busy = true);
    try {
      final r = await _api.call('/m09/render', userId: DemoUsers.outfits, payload: {
        'sex': _sex,
        'height_cm': _height.round(),
        'weight_kg': _weight.round(),
        'piece_ids': _picked.toList(),
      });
      setState(() => _render = r);
    } catch (e) {
      if (mounted) dmToast(context, apiError(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _open(String url) => launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);

  @override
  Widget build(BuildContext context) {
    final r = _render;
    return DmPage(
      eyebrow: 'BO9 · Try it on',
      title: 'See it on you',
      trailing: IconButton(
        tooltip: 'Open the 3D studio',
        onPressed: () => _open('${_api.base}/m09/demo'),
        icon: const Icon(Icons.view_in_ar_rounded, color: Colors.white),
      ),
      children: [
        DmCard(
          onTap: () => context.go('/bo9_avatar'),
          child: const Row(children: [
            Icon(Icons.view_in_ar_outlined, color: DmColors.bronze),
            SizedBox(width: 12),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('My 3D avatar', style: DmText.cardTitle),
                Text("Nadhir's SMPL-X studio: build your body (thin → heavy), details, photos.", style: DmText.caption),
              ]),
            ),
            Icon(Icons.chevron_right_rounded, color: DmColors.muted),
          ]),
        ),
        const SizedBox(height: 12),
        DmCard(
          big: true,
          padding: const EdgeInsets.all(18),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const DmSectionHeader(eyebrow: 'Your body', title: 'Faceless avatar'),
            const SizedBox(height: 10),
            Row(children: [
              DmChoiceChip(label: 'Woman', selected: _sex == 'female', onTap: () => setState(() => _sex = 'female')),
              const SizedBox(width: 6),
              DmChoiceChip(label: 'Man', selected: _sex == 'male', onTap: () => setState(() => _sex = 'male')),
            ]),
            const SizedBox(height: 8),
            Text('Height ${_height.round()} cm', style: DmText.body),
            Slider(value: _height, min: 140, max: 205, onChanged: (v) => setState(() => _height = v)),
            Text('Weight ${_weight.round()} kg', style: DmText.body),
            Slider(value: _weight, min: 40, max: 140, onChanged: (v) => setState(() => _weight = v)),
          ]),
        ),
        const SizedBox(height: 14),
        const DmSectionHeader(eyebrow: 'Your 3D pieces', title: 'Pick what to wear'),
        const SizedBox(height: 8),
        DmLoad(
          load: () => _api.get('/m09/pieces', query: {'user_id': DemoUsers.outfits}),
          builder: (d, reload) {
            final pieces = jsonList(((d['result'] as Map?) ?? d)['pieces']);
            if (pieces.isEmpty) {
              return DmCard(
                child: DmEmptyState(
                  icon: Icons.checkroom,
                  title: 'No 3D piece yet',
                  message: 'Add pieces from photos in the 3D studio, then come back. You can still render your avatar.',
                  action: DmButton('Open the 3D studio', kind: DmButtonKind.outline, onPressed: () => _open('${_api.base}/m09/demo')),
                ),
              );
            }
            return Wrap(spacing: 6, runSpacing: 6, children: [
              for (final p in pieces)
                DmChoiceChip(
                  label: '${p['name'] ?? p['type'] ?? p['piece_id']}',
                  selected: _picked.contains('${p['piece_id'] ?? p['id']}'),
                  onTap: () => setState(() {
                    final id = '${p['piece_id'] ?? p['id']}';
                    _picked.contains(id) ? _picked.remove(id) : _picked.add(id);
                  }),
                ),
            ]);
          },
        ),
        const SizedBox(height: 14),
        DmButton(_busy ? 'Dressing your avatar…' : 'Show it on me', kind: DmButtonKind.gold, icon: Icons.accessibility_new_rounded,
            onPressed: _busy ? null : _go),
        if (r != null) ...[
          const SizedBox(height: 14),
          DmCard(
            big: true,
            padding: const EdgeInsets.all(18),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                const Expanded(child: Text('Your avatar', style: DmText.title)),
                DmSource(mocked: r['_mocked'] == true, label: 'M9'),
              ]),
              const SizedBox(height: 8),
              Wrap(spacing: 6, runSpacing: 6, children: [
                for (final e in ((r['body'] as Map?) ?? const {}).entries) DmPill('${e.key.toString().replaceAll('_cm', '')} ${e.value} cm'),
                for (final g in (r['garments'] as List? ?? const [])) DmPill('wears $g', dark: true),
              ]),
              if ((r['sizing'] as Map?)?.isNotEmpty ?? false) ...[
                const SizedBox(height: 8),
                Text('Fit: ${r['sizing']}', style: DmText.body),
              ],
              const SizedBox(height: 12),
              if (r['glb_url'] != null)
                DmButton('Open in 3D', kind: DmButtonKind.dark, icon: Icons.view_in_ar_rounded,
                    onPressed: () => _open(_api.media('${r['glb_url']}')))
              else
                Text(r['_mocked'] == true
                    ? 'M9 runs on its mock here (no Blender on this machine): measurements only, no 3D file.'
                    : 'No 3D file returned.', style: DmText.caption),
            ]),
          ),
        ],
      ],
    );
  }
}
