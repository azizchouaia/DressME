// Owner: BO4 (Amine) — "My style": M5 adaptive style profile, as Amine presents it (/m05/ui):
// 10 swipe cards at first open (no question), then daily batches of 10 outfits ranked by the learnt taste
// (M2 proposes, M5 chooses) with 2 "Discovery" cards, every swipe sent to /m05/feedback, the panel
// "what M5 learnt" and the style coach agent.
import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/dm_api.dart';
import '../../../core/design/dressme_design.dart';
import '../../../core/widgets/dm_widgets.dart';

const _occasions = {'work': 'Work', 'uni': 'University', 'casual': 'Casual', 'event': 'Event', 'sport': 'Sport'};

class MyStyleScreen extends ConsumerStatefulWidget {
  const MyStyleScreen({super.key});

  @override
  ConsumerState<MyStyleScreen> createState() => _MyStyleScreenState();
}

class _MyStyleScreenState extends ConsumerState<MyStyleScreen> {
  DmApi get api => ref.read(dmApiProvider);
  String get user => DemoUsers.wardrobe;

  Json? styles; // /m05/styles: labels + family colours
  Json? profile; // null = no profile yet
  Json? explain;
  List<Json>? cards; // the deck on screen
  bool onboarding = true;
  bool loading = true;
  String? error;
  String meta = '';
  int liked = 0;
  int total = 0;
  bool batchDone = false;

  // daily context
  double temp = 22;
  String occasion = 'work';
  bool rain = false;
  bool weekend = false;

  // swipes are queued and sent in the background, like Amine's page
  final _queue = <Json>[];
  Timer? _flushTimer;

  @override
  void initState() {
    super.initState();
    _boot();
  }

  @override
  void dispose() {
    _flushTimer?.cancel();
    _flush();
    super.dispose();
  }

  String styleLabel(String id) =>
      '${(jsonList(styles?['styles']).firstWhere((s) => s['id'] == id, orElse: () => {'label': id}))['label'] ?? id}';
  String familyLabel(String f) => '${((styles?['families'] as Map?)?[f] as Map?)?['label'] ?? f}';
  Color familyColour(String f) {
    final hex = '${((styles?['families'] as Map?)?[f] as Map?)?['colour'] ?? '#999999'}'.replaceAll('#', '');
    return Color(int.tryParse('FF$hex', radix: 16) ?? 0xFF999999);
  }

  Future<void> _boot() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      styles = await api.get('/m05/styles');
      await _refreshPanel();
      if (profile?['onboarded'] == true) {
        onboarding = false;
        cards = null;
      } else {
        await _loadOnboarding();
      }
    } catch (e) {
      error = apiError(e);
    }
    if (mounted) setState(() => loading = false);
  }

  Future<void> _refreshPanel() async {
    try {
      final p = await api.get('/m05/profile/$user');
      final e = await api.get('/m05/explain/$user', query: {'k': 5});
      if (mounted) {
        setState(() {
          profile = p;
          explain = e;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          profile = null;
          explain = null;
        });
      }
    }
  }

  Future<void> _loadOnboarding() async {
    final r = await api.get('/m05/onboarding/swipe-cards', query: {'user_id': user});
    setState(() {
      onboarding = true;
      cards = jsonList(r['cards']);
      liked = 0;
      total = cards!.length;
      batchDone = false;
      meta = '${r['n_candidates']} candidates (${r['candidates_source']}) · ${r['elapsed_ms']} ms';
    });
  }

  Future<void> _loadDaily() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final r = await api.post('/m05/choose', {
        'user_id': user,
        'context': {'temp_c': temp.round(), 'rain': rain, 'occasion': occasion, 'weekend': weekend},
      });
      setState(() {
        onboarding = false;
        cards = jsonList(r['cards']);
        liked = 0;
        total = cards!.length;
        batchDone = false;
        meta = '${r['n_candidates']} candidate outfits (${r['candidates_source']}) → ${cards!.length} cards · ${r['elapsed_ms']} ms';
      });
      _refreshPanel();
    } catch (e) {
      setState(() => error = apiError(e));
    }
    if (mounted) setState(() => loading = false);
  }

  void _react(Json card, String reaction) {
    if (const {'like', 'accept', 'heart'}.contains(reaction)) liked++;
    _queue.add({'log_id': card['log_id'], 'reaction': reaction, 'source': onboarding ? 'onboarding' : 'swipe'});
    _flushTimer?.cancel();
    _flushTimer = Timer(const Duration(milliseconds: 1200), _flush);
    if (_queue.length >= 5) _flush();
  }

  Future<void> _flush() async {
    if (_queue.isEmpty) return;
    final events = List<Json>.of(_queue);
    _queue.clear();
    try {
      await api.post('/m05/feedback', {'user_id': user, 'events': events});
      if (mounted) _refreshPanel();
    } catch (e) {
      _queue.insertAll(0, events); // try again with the next swipe
    }
  }

  Future<void> _done() async {
    await _flush();
    setState(() => batchDone = true);
  }

  Future<void> _reset() async {
    try {
      await api.delete('/m05/profile/$user');
    } catch (_) {}
    await _boot();
  }

  // ---------------------------------------------------------------- UI

  @override
  Widget build(BuildContext context) {
    final onboarded = profile?['onboarded'] == true;
    return Scaffold(
      backgroundColor: DmColors.page,
      floatingActionButton: onboarded
          ? FloatingActionButton.extended(
              backgroundColor: DmColors.inkDeep,
              foregroundColor: DmColors.goldLight,
              onPressed: () => showModalBottomSheet<void>(
                context: context,
                isScrollControlled: true,
                backgroundColor: Colors.transparent,
                builder: (_) => _Coach(user: user, onChanged: _refreshPanel),
              ),
              icon: const Icon(Icons.auto_awesome),
              label: const Text('Style coach'),
            )
          : null,
      body: ListView(padding: EdgeInsets.zero, children: [
        DmHero(
          eyebrow: 'BO4 · Module M5 · Adaptive style profile',
          title: 'Your style, learnt swipe after swipe',
          trailing: IconButton(
            tooltip: 'Reset my style profile',
            onPressed: _reset,
            icon: const Icon(Icons.restart_alt_rounded, color: Colors.white),
          ),
          child: Text(
            'No questions: swipe right what you like, left the rest. Then 10 outfits a day from your wardrobe, '
            'ranked by your taste, with 2 "Discovery" cards.',
            style: DmText.body.copyWith(color: DmColors.goldLight),
          ),
        ),
        Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 1000),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 18, 16, 90),
              child: LayoutBuilder(builder: (context, box) {
                final wide = box.maxWidth >= 820;
                final phone = _phone();
                final panel = _Panel(profile: profile, explain: explain, meta: meta, state: this);
                return wide
                    ? Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        SizedBox(width: 420, child: phone),
                        const SizedBox(width: 18),
                        Expanded(child: panel),
                      ])
                    : Column(children: [phone, const SizedBox(height: 18), panel]);
              }),
            ),
          ),
        ),
      ]),
    );
  }

  Widget _steps() => Row(children: [
        for (final (i, label) in const [(0, 'Swipes'), (1, 'Daily')])
          Expanded(
            child: Container(
              margin: EdgeInsets.only(right: i == 0 ? 6 : 0),
              height: 4,
              decoration: BoxDecoration(
                color: (onboarding ? 0 : 1) >= i ? DmColors.gold : DmColors.border,
                borderRadius: BorderRadius.circular(2),
              ),
              child: Tooltip(message: label),
            ),
          ),
      ]);

  Widget _phone() {
    Widget body;
    if (loading) {
      body = const Padding(padding: EdgeInsets.all(60), child: Center(child: CircularProgressIndicator()));
    } else if (error != null) {
      body = DmEmptyState(icon: Icons.wifi_off_rounded, title: 'M5 is not answering', message: error!,
          action: DmButton('Try again', onPressed: _boot));
    } else if (onboarding) {
      body = batchDone
          ? _thanks()
          : Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Text('YOUR STYLE · ${cards?.length ?? 0} CARDS', style: DmText.eyebrow),
              const SizedBox(height: 4),
              const Text('Do you like this look?', style: DmText.title),
              const SizedBox(height: 14),
              _Deck(key: ValueKey('onb-${cards.hashCode}'), cards: cards ?? const [], onboarding: true, state: this),
            ]);
    } else {
      body = Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const Text('DAILY SUGGESTIONS', style: DmText.eyebrow),
        const SizedBox(height: 4),
        const Text('Your 10 outfits', style: DmText.title),
        const SizedBox(height: 12),
        _context(),
        const SizedBox(height: 12),
        if (cards == null || batchDone) ...[
          if (batchDone)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Text('$liked / $total outfits liked in this batch.', style: DmText.body),
            ),
          DmButton(batchDone ? '10 more outfits' : 'Get 10 outfits', kind: DmButtonKind.gold, icon: Icons.style_outlined,
              onPressed: _loadDaily),
        ] else if (cards!.isEmpty)
          const Padding(
              padding: EdgeInsets.all(20),
              child: Text('No outfit possible with this wardrobe and this context. Add pieces in your wardrobe.',
                  style: DmText.body, textAlign: TextAlign.center))
        else
          _Deck(key: ValueKey('day-${cards.hashCode}'), cards: cards!, onboarding: false, state: this),
      ]);
    }
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(DmRadius.hero),
        border: Border.all(color: DmColors.border),
        boxShadow: const [BoxShadow(color: Color(0x14000000), blurRadius: 24, offset: Offset(0, 10))],
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        _steps(),
        const SizedBox(height: 16),
        AnimatedSwitcher(duration: const Duration(milliseconds: 300), child: KeyedSubtree(key: ValueKey('$onboarding$batchDone$loading'), child: body)),
      ]),
    );
  }

  Widget _thanks() => Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const Icon(Icons.favorite_rounded, color: DmColors.gold, size: 42),
        const SizedBox(height: 10),
        Text('Thank you! $liked card${liked == 1 ? '' : 's'} liked out of $total.',
            style: DmText.title, textAlign: TextAlign.center),
        const SizedBox(height: 6),
        const Text('Your profile is ready. Now the outfits of the day.', style: DmText.body, textAlign: TextAlign.center),
        const SizedBox(height: 16),
        DmButton('See my outfits of the day', kind: DmButtonKind.gold, onPressed: () {
          setState(() {
            onboarding = false;
            batchDone = false;
            cards = null;
          });
          _loadDaily();
        }),
      ]);

  Widget _context() => Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Row(children: [
          Icon(rain ? Icons.water_drop_outlined : (temp >= 25 ? Icons.wb_sunny_outlined : (temp < 12 ? Icons.ac_unit : Icons.cloud_outlined)),
              size: 18, color: DmColors.bronze),
          Expanded(
            child: Slider(
              value: temp,
              min: -5,
              max: 42,
              divisions: 47,
              activeColor: DmColors.gold,
              label: '${temp.round()} °C',
              onChanged: (v) => setState(() => temp = v),
            ),
          ),
          Text('${temp.round()} °C', style: DmText.body.copyWith(fontWeight: FontWeight.w700)),
        ]),
        Wrap(spacing: 6, runSpacing: 6, children: [
          for (final e in _occasions.entries)
            DmChoiceChip(label: e.value, selected: occasion == e.key, onTap: () => setState(() => occasion = e.key)),
        ]),
        const SizedBox(height: 6),
        Row(children: [
          FilterChip(label: const Text('Rain'), selected: rain, onSelected: (v) => setState(() => rain = v)),
          const SizedBox(width: 8),
          FilterChip(label: const Text('Weekend'), selected: weekend, onSelected: (v) => setState(() => weekend = v)),
        ]),
      ]);
}

/// The swipe deck: two stacked cards, drag the top one (right = like / yes, left = no, up = love),
/// or use the round buttons. Stamps "I LIKE" / "NO" appear while dragging, like Amine's page.
class _Deck extends StatefulWidget {
  const _Deck({super.key, required this.cards, required this.onboarding, required this.state});

  final List<Json> cards;
  final bool onboarding;
  final _MyStyleScreenState state;

  @override
  State<_Deck> createState() => _DeckState();
}

class _DeckState extends State<_Deck> with SingleTickerProviderStateMixin {
  int index = 0;
  Offset drag = Offset.zero;
  late final AnimationController _out = AnimationController(vsync: this, duration: const Duration(milliseconds: 260));
  Offset _from = Offset.zero;
  Offset _to = Offset.zero;
  List<Json>? why;

  @override
  void dispose() {
    _out.dispose();
    super.dispose();
  }

  Offset get _pos => _out.isAnimating || _out.value > 0 ? Offset.lerp(_from, _to, Curves.easeIn.transform(_out.value))! : drag;

  Future<void> _decide(String reaction) async {
    if (index >= widget.cards.length || _out.isAnimating) return;
    final card = widget.cards[index];
    _from = drag;
    _to = switch (reaction) {
      'reject' => const Offset(-600, 40),
      'ignored' => const Offset(0, -700),
      'heart' => const Offset(0, -700),
      _ => const Offset(600, 40),
    };
    widget.state._react(card, reaction);
    await _out.forward(from: 0);
    if (!mounted) return;
    setState(() {
      index++;
      drag = Offset.zero;
      why = null;
      _out.value = 0;
    });
    if (index >= widget.cards.length) widget.state._done();
  }

  Future<void> _why() async {
    final card = widget.cards[index];
    await widget.state._flush();
    try {
      final e = await widget.state.api.get('/m05/explain/${widget.state.user}', query: {'log_id': card['log_id'], 'k': 4});
      if (mounted) setState(() => why = jsonList(e['card']));
    } catch (e) {
      if (mounted) dmToast(context, apiError(e));
    }
  }

  @override
  Widget build(BuildContext context) {
    final cards = widget.cards;
    final left = cards.length - index;
    final top = left > 0 ? cards[index] : null;
    final next = left > 1 ? cards[index + 1] : null;
    final p = _pos;
    final reactions = widget.onboarding
        ? const [('reject', Icons.close_rounded, 'No (←)', DmColors.warning), ('like', Icons.favorite_rounded, 'I like (→)', Color(0xFFD0587E))]
        : const [
            ('reject', Icons.close_rounded, 'No (←)', DmColors.warning),
            ('ignored', Icons.redo_rounded, 'Skip (↓)', DmColors.muted),
            ('accept', Icons.check_rounded, 'Yes (→)', DmColors.success),
            ('heart', Icons.favorite_rounded, 'Love it (↑)', Color(0xFFD0587E)),
          ];
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        Text('${math.min(index + 1, cards.length)} / ${cards.length}', style: DmText.caption),
        Text('${widget.state.liked} liked', style: DmText.caption),
      ]),
      const SizedBox(height: 6),
      ClipRRect(
        borderRadius: BorderRadius.circular(3),
        child: LinearProgressIndicator(
          value: cards.isEmpty ? 0 : index / cards.length,
          minHeight: 4,
          backgroundColor: DmColors.border,
          valueColor: const AlwaysStoppedAnimation(DmColors.gold),
        ),
      ),
      const SizedBox(height: 14),
      SizedBox(
        height: 440,
        child: Stack(clipBehavior: Clip.none, alignment: Alignment.center, children: [
          if (next != null)
            Transform.scale(scale: .95, child: Transform.translate(offset: const Offset(0, 14), child: _CardView(card: next, state: widget.state))),
          if (top != null)
            AnimatedBuilder(
              animation: _out,
              builder: (_, __) => GestureDetector(
                onPanUpdate: (d) => setState(() => drag += d.delta),
                onPanEnd: (_) {
                  if (drag.dx > 90) {
                    _decide(widget.onboarding ? 'like' : 'accept');
                  } else if (drag.dx < -90) {
                    _decide('reject');
                  } else if (!widget.onboarding && drag.dy < -110) {
                    _decide('heart');
                  } else {
                    setState(() => drag = Offset.zero);
                  }
                },
                child: Transform.translate(
                  offset: Offset(p.dx, math.min(p.dy, 0) * .4 + (p.dy < 0 && !widget.onboarding ? p.dy * .6 : 0)),
                  child: Transform.rotate(
                    angle: p.dx / 18 * math.pi / 180,
                    child: _CardView(
                      card: top,
                      state: widget.state,
                      yes: (p.dx / 90).clamp(0.0, 1.0),
                      no: (-p.dx / 90).clamp(0.0, 1.0),
                    ),
                  ),
                ),
              ),
            ),
        ]),
      ),
      const SizedBox(height: 16),
      Row(mainAxisAlignment: MainAxisAlignment.center, children: [
        for (final (r, icon, label, colour) in reactions)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8),
            child: Tooltip(
              message: label,
              child: Material(
                color: Colors.white,
                shape: CircleBorder(side: BorderSide(color: colour.withValues(alpha: .4))),
                elevation: 2,
                child: InkWell(
                  customBorder: const CircleBorder(),
                  onTap: top == null ? null : () => _decide(r),
                  child: Padding(
                    padding: EdgeInsets.all(r == 'ignored' ? 11 : 15),
                    child: Icon(icon, color: colour, size: r == 'ignored' ? 20 : 26),
                  ),
                ),
              ),
            ),
          ),
      ]),
      if (!widget.onboarding && top != null) ...[
        const SizedBox(height: 10),
        TextButton.icon(onPressed: _why, icon: const Icon(Icons.help_outline_rounded, size: 18), label: const Text('Why this outfit?')),
        if (why != null)
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(color: DmColors.sand, borderRadius: BorderRadius.circular(DmRadius.small)),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('What counted for this card', style: DmText.cardTitle),
              const SizedBox(height: 6),
              for (final r in why!)
                Text('${(r['weight'] as num? ?? 0) >= 0 ? '＋' : '－'} ${r['label']}', style: DmText.body),
            ]),
          ),
      ],
    ]);
  }
}

class _CardView extends StatelessWidget {
  const _CardView({required this.card, required this.state, this.yes = 0, this.no = 0});

  final Json card;
  final _MyStyleScreenState state;
  final double yes;
  final double no;

  Widget _img(String src) {
    final url = state.api.media(src);
    if (url.toLowerCase().contains('.svg')) {
      // drawn reference look (SVG): shown as a soft illustration tile
      return Container(
        color: DmColors.sand,
        child: const Center(child: Icon(Icons.checkroom_rounded, size: 72, color: DmColors.bar)),
      );
    }
    return Image.network(url, fit: BoxFit.contain, errorBuilder: (_, __, ___) => const Icon(Icons.image_not_supported_outlined));
  }

  @override
  Widget build(BuildContext context) {
    final imgs = [for (final i in (card['images'] as List? ?? const [])) '$i'].take(4).toList();
    final ctx = (card['context'] as Map?)?.cast<String, dynamic>() ?? const {};
    final t = (ctx['temp_c'] as num?)?.round() ?? 20;
    final title = '${card['title'] ?? 'Outfit · ${(card['item_ids'] as List? ?? const []).length} pieces'}';
    Widget media;
    if (imgs.length <= 1) {
      media = imgs.isEmpty ? const SizedBox() : _img(imgs.first);
    } else {
      media = GridView.count(
        crossAxisCount: 2,
        physics: const NeverScrollableScrollPhysics(),
        padding: const EdgeInsets.all(8),
        mainAxisSpacing: 6,
        crossAxisSpacing: 6,
        children: [for (final s in imgs) ClipRRect(borderRadius: BorderRadius.circular(10), child: Container(color: DmColors.page, child: _img(s)))],
      );
    }
    Widget stamp(String text, Color c, double o, double angle, Alignment a) => Align(
          alignment: a,
          child: Opacity(
            opacity: o,
            child: Transform.rotate(
              angle: angle,
              child: Container(
                margin: const EdgeInsets.all(18),
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                decoration: BoxDecoration(border: Border.all(color: c, width: 3), borderRadius: BorderRadius.circular(8)),
                child: Text(text, style: DmText.title.copyWith(color: c, letterSpacing: 2)),
              ),
            ),
          ),
        );
    return Container(
      width: 360,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(DmRadius.panel),
        border: Border.all(color: DmColors.border),
        boxShadow: const [BoxShadow(color: Color(0x1F000000), blurRadius: 18, offset: Offset(0, 8))],
      ),
      clipBehavior: Clip.antiAlias,
      child: Stack(children: [
        Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Expanded(child: Container(color: DmColors.page, child: media)),
          Padding(
            padding: const EdgeInsets.all(14),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Wrap(spacing: 6, runSpacing: 4, children: [
                _tag('${ctx['rain'] == true ? '🌧' : t >= 25 ? '☀️' : t < 12 ? '❄️' : '⛅'} $t °C'),
                _tag(_occasions[ctx['occasion']] ?? '${ctx['occasion'] ?? ''}'),
                _tag(ctx['weekend'] == true ? 'Weekend' : 'Weekday'),
                if (card['explore'] == true)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(color: DmColors.inkDeep, borderRadius: BorderRadius.circular(DmRadius.pill)),
                    child: Text('Discovery', style: DmText.caption.copyWith(color: DmColors.goldLight, fontWeight: FontWeight.w700)),
                  ),
              ]),
              const SizedBox(height: 8),
              Text(title, style: DmText.cardTitle, maxLines: 1, overflow: TextOverflow.ellipsis),
              const SizedBox(height: 4),
              Text(
                [for (final s in jsonList(card['top_styles'])) '${state.styleLabel('${s['style']}')} ${pct(s['share'])}'].join(' · '),
                style: DmText.caption,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ]),
          ),
        ]),
        stamp('I LIKE', DmColors.success, yes, -.2, Alignment.topLeft),
        stamp('NO', DmColors.warning, no, .2, Alignment.topRight),
      ]),
    );
  }

  Widget _tag(String s) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(color: DmColors.sand, borderRadius: BorderRadius.circular(DmRadius.pill)),
        child: Text(s, style: DmText.caption),
      );
}

/// "What M5 learnt": style families (bars), top styles, strongest rules, facts.
class _Panel extends StatelessWidget {
  const _Panel({required this.profile, required this.explain, required this.meta, required this.state});

  final Json? profile;
  final Json? explain;
  final String meta;
  final _MyStyleScreenState state;

  @override
  Widget build(BuildContext context) {
    final p = profile;
    final n = (p?['n_feedback'] as num?)?.toInt() ?? 0;
    return DmCard(
      big: true,
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Row(children: [
          const Expanded(child: Text('What M5 learnt', style: DmText.cardTitle)),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(color: DmColors.sandDark, borderRadius: BorderRadius.circular(DmRadius.pill)),
            child: Text('$n feedback${n == 1 ? '' : 's'}', style: DmText.caption.copyWith(fontWeight: FontWeight.w700)),
          ),
        ]),
        const SizedBox(height: 12),
        if (p == null)
          const Text('No profile yet. It builds up from the first swipes.', style: DmText.body)
        else ...[
          const Text('STYLE FAMILIES', style: DmText.eyebrow),
          const SizedBox(height: 8),
          for (final e in ((p['families'] as Map?) ?? const {}).entries.toList()
            ..sort((a, b) => ((b.value as num?) ?? 0).compareTo((a.value as num?) ?? 0)))
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(children: [
                SizedBox(width: 90, child: Text(state.familyLabel('${e.key}'), style: DmText.caption)),
                Expanded(
                  child: TweenAnimationBuilder<double>(
                    tween: Tween(begin: 0, end: ((e.value as num?) ?? 0).toDouble().clamp(0, 1)),
                    duration: const Duration(milliseconds: 600),
                    curve: Curves.easeOutCubic,
                    builder: (_, v, __) => ClipRRect(
                      borderRadius: BorderRadius.circular(4),
                      child: LinearProgressIndicator(
                        value: v,
                        minHeight: 8,
                        backgroundColor: DmColors.border,
                        valueColor: AlwaysStoppedAnimation(state.familyColour('${e.key}')),
                      ),
                    ),
                  ),
                ),
                SizedBox(width: 44, child: Text(pct(e.value), textAlign: TextAlign.right, style: DmText.caption)),
              ]),
            ),
          const SizedBox(height: 10),
          const Text('TOP STYLES', style: DmText.eyebrow),
          const SizedBox(height: 8),
          Wrap(spacing: 6, runSpacing: 6, children: [
            for (final s in jsonList(p['top_styles']))
              Chip(
                avatar: CircleAvatar(backgroundColor: state.familyColour('${s['family']}'), radius: 6),
                label: Text('${state.styleLabel('${s['style']}')} · ${pct(s['share'])}'),
              ),
            if (jsonList(p['top_styles']).isEmpty) const Text('after the first like', style: DmText.caption),
          ]),
          const SizedBox(height: 10),
          const Text('STRONGEST RULES', style: DmText.eyebrow),
          const SizedBox(height: 6),
          for (final r in jsonList(explain?['positive']))
            Text('＋ ${r['label']}  (${((r['weight'] as num?) ?? 0).toStringAsFixed(2)})', style: DmText.body.copyWith(color: DmColors.success)),
          for (final r in jsonList(explain?['negative']))
            Text('－ ${r['label']}  (${((r['weight'] as num?) ?? 0).toStringAsFixed(2)})', style: DmText.body.copyWith(color: DmColors.warning)),
          const SizedBox(height: 10),
          const Text('PROFILE', style: DmText.eyebrow),
          const SizedBox(height: 6),
          Text('Onboarding: ${p['onboarded'] == true ? 'done' : 'in progress'}', style: DmText.body),
          Text('Want more: ${_styles((p['answers'] as Map?)?['want_more'])}', style: DmText.body),
          Text('Want less: ${_styles((p['answers'] as Map?)?['want_less'])}', style: DmText.body),
          Text('Taste vector: ${p['taste_vector'] is List ? '${(p['taste_vector'] as List).length} dimensions' : 'after the first like'}',
              style: DmText.body),
        ],
        if (meta.isNotEmpty) ...[const SizedBox(height: 10), Text(meta, style: DmText.caption)],
      ]),
    );
  }

  String _styles(Object? ids) {
    final l = [for (final i in (ids as List? ?? const [])) state.styleLabel('$i')];
    return l.isEmpty ? '—' : l.join(', ');
  }
}

/// The style coach agent (POST /m05/agent/chat): explains the profile and adjusts it ("more classic").
class _Coach extends ConsumerStatefulWidget {
  const _Coach({required this.user, required this.onChanged});

  final String user;
  final VoidCallback onChanged;

  @override
  ConsumerState<_Coach> createState() => _CoachState();
}

class _CoachState extends ConsumerState<_Coach> {
  final _input = TextEditingController();
  final _log = <(bool, String, List<String>)>[]; // (me, text, tools)
  String? thread;
  bool busy = false;

  @override
  void dispose() {
    _input.dispose();
    super.dispose();
  }

  Future<void> _send([String? text]) async {
    final msg = (text ?? _input.text).trim();
    if (msg.isEmpty || busy) return;
    _input.clear();
    setState(() {
      _log.add((true, msg, const []));
      busy = true;
    });
    try {
      final r = await ref.read(dmApiProvider).post('/m05/agent/chat', {'user_id': widget.user, 'message': msg, 'thread_id': thread});
      thread = '${r['thread_id']}';
      setState(() => _log.add((false, '${r['reply']}', [for (final s in jsonList(r['steps'])) '${s['tool']}'])));
      if (r['profile_changed'] == true) widget.onChanged();
    } catch (e) {
      setState(() => _log.add((false, apiError(e), const [])));
    }
    if (mounted) setState(() => busy = false);
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: Container(
        height: MediaQuery.of(context).size.height * .75,
        decoration: const BoxDecoration(color: DmColors.page, borderRadius: BorderRadius.vertical(top: Radius.circular(DmRadius.hero))),
        padding: const EdgeInsets.fromLTRB(18, 16, 18, 14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Row(children: [
            const Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('Style coach', style: DmText.title),
                Text('M5 agent · local LLM', style: DmText.caption),
              ]),
            ),
            TextButton(onPressed: () => setState(() {
                  _log.clear();
                  thread = null;
                }), child: const Text('New conversation')),
            IconButton(onPressed: () => Navigator.pop(context), icon: const Icon(Icons.close_rounded)),
          ]),
          const Divider(),
          Expanded(
            child: _log.isEmpty
                ? Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    const Text('Ask for example:', style: DmText.caption),
                    const SizedBox(height: 8),
                    Wrap(spacing: 6, runSpacing: 6, children: [
                      for (final s in const ['Why do you show me streetwear? I want more classic.', 'What is my style?', 'An outfit for work tomorrow, 15 °C.'])
                        ActionChip(label: Text(s), onPressed: () => _send(s)),
                    ]),
                  ])
                : ListView(children: [
                    for (final (me, text, tools) in _log)
                      Align(
                        alignment: me ? Alignment.centerRight : Alignment.centerLeft,
                        child: Container(
                          constraints: const BoxConstraints(maxWidth: 520),
                          margin: const EdgeInsets.only(bottom: 8),
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: me ? DmColors.inkDeep : Colors.white,
                            borderRadius: BorderRadius.circular(DmRadius.card),
                            border: me ? null : Border.all(color: DmColors.border),
                          ),
                          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            Text(text, style: DmText.body.copyWith(color: me ? Colors.white : DmColors.text)),
                            if (tools.isNotEmpty) ...[
                              const SizedBox(height: 4),
                              Text('tools: ${tools.join(' → ')}', style: DmText.caption),
                            ],
                          ]),
                        ),
                      ),
                    if (busy) const Padding(padding: EdgeInsets.all(8), child: LinearProgressIndicator()),
                  ]),
          ),
          Row(children: [
            Expanded(
              child: TextField(
                controller: _input,
                onSubmitted: (_) => _send(),
                decoration: const InputDecoration(hintText: 'Write in English, French or Arabic…'),
              ),
            ),
            const SizedBox(width: 8),
            IconButton.filled(onPressed: busy ? null : _send, icon: const Icon(Icons.send_rounded)),
          ]),
        ]),
      ),
    );
  }
}
