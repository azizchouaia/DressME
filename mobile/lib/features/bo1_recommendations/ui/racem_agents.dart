// Owner: BO1 / BO2 (Racem) — the app side of Racem's agents, as he presents them in /bo/screens and /bo/demo:
// buttons call an idea agent directly (POST /bo/chat with an action, no LLM), the result shows the pieces /
// outfits, and "How it worked" draws who called whom (BO agent -> idea agent -> tools). A chat tab talks to the
// BO agent in plain language (local LLM) and shows its pipeline (memory -> routing -> idea agent -> tools -> answer).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/dm_api.dart';
import '../../../core/design/dressme_design.dart';
import '../../../core/widgets/dm_widgets.dart';

/// One button of a screen: idea agent + action (+ args). [viaBo] = sent to that BO agent first (cross-BO).
class AgentButton {
  const AgentButton(this.label, this.agent, this.action, {this.args = const {}, this.viaBo, this.fromOutfit = false});

  final String label;
  final String agent;
  final String action;
  final Map<String, Object> args;
  final String? viaBo;
  final bool fromOutfit; // sends the pieces of the last outfit (e.g. "Outfit -> laundry")
}

class AgentSection {
  const AgentSection(this.title, this.tag, this.buttons, {this.note});

  final String title;
  final String tag; // "BO2 · daily_plan"
  final List<AgentButton> buttons;
  final String? note;
}

/// The whole BO page: hero, the screens (button sections) + result + how it worked, and the chat tab.
class RacemBoPage extends ConsumerStatefulWidget {
  const RacemBoPage({super.key, required this.eyebrow, required this.title, required this.boAgent, required this.sections, required this.examples});

  final String eyebrow;
  final String title;
  final String boAgent; // personalised_recommendations | time_optimisation
  final List<AgentSection> sections;
  final List<String> examples;

  @override
  ConsumerState<RacemBoPage> createState() => _RacemBoPageState();
}

class _RacemBoPageState extends ConsumerState<RacemBoPage> {
  final session = 'app-${DateTime.now().millisecondsSinceEpoch}';
  Map<String, Json> catalog = {};
  String? catalogSource;
  String? catalogError;
  bool chat = false;
  bool busy = false;
  String? running;
  Json? result; // {button, agent, action, data, question, error, steps, seconds}
  List<String> lastIds = [];

  DmApi get api => ref.read(dmApiProvider);
  String get user => DemoUsers.outfits;

  @override
  void initState() {
    super.initState();
    _loadCatalog();
  }

  Future<void> _loadCatalog() async {
    try {
      final c = await api.get('/bo/catalog', query: {'user_id': user});
      setState(() {
        catalog = {for (final e in ((c['pieces'] as Map?) ?? const {}).entries) '${e.key}': (e.value as Map).cast<String, dynamic>()};
        catalogSource = c['source'] as String?;
      });
    } catch (e) {
      setState(() => catalogError = apiError(e));
    }
  }

  Future<void> _tap(AgentButton b) async {
    var args = Map<String, Object?>.from(b.args);
    if (b.fromOutfit) {
      final names = lastIds.map((id) => catalog[id]?['name']).whereType<String>().toList();
      if (names.isEmpty) {
        dmToast(context, 'Get an outfit first.');
        return;
      }
      args = {'pieces': names.join(', ')};
    }
    final body = b.viaBo != null
        ? {'agent': b.viaBo, 'user_id': user, 'session_id': session, 'message': '',
            'payload': {'action': '${b.agent}.${b.action}', 'args': args, 'reply': false}}
        : {'agent': b.agent, 'user_id': user, 'session_id': session, 'message': '',
            'payload': {'action': b.action, 'args': args, 'reply': false}};
    setState(() {
      busy = true;
      running = b.label;
    });
    final t0 = DateTime.now();
    try {
      final r = await api.post('/bo/chat', body);
      final res = ((r['result'] as Map?) ?? const {}).cast<String, dynamic>();
      final data = ((res['data'] as Map?) ?? const {}).cast<String, dynamic>();
      final outs = outfitsOf(data);
      if (outs.isNotEmpty) lastIds = outs.first.$1;
      if (data['before'] is List && data['after'] is List) {
        lastIds = [for (final n in data['after'] as List) _idOfName('$n')].whereType<String>().toList();
      }
      setState(() => result = {
            'button': b.label,
            'first': b.viaBo ?? b.agent,
            'agent': b.agent,
            'action': b.viaBo != null ? '${b.agent}.${b.action}' : b.action,
            'data': data,
            'question': r['question'],
            'error': res['error'],
            'steps': res['steps'] ?? const [],
            'seconds': DateTime.now().difference(t0).inMilliseconds / 1000,
          });
    } catch (e) {
      setState(() => result = {'button': b.label, 'error': apiError(e), 'data': <String, dynamic>{}, 'steps': const []});
    } finally {
      if (mounted) {
        setState(() {
          busy = false;
          running = null;
        });
      }
    }
  }

  String? _idOfName(String n) {
    for (final e in catalog.entries) {
      if (e.value['name'] == n) return e.key;
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: DmColors.page,
      body: ListView(padding: EdgeInsets.zero, children: [
        DmHero(
          eyebrow: widget.eyebrow,
          title: widget.title,
          child: Wrap(spacing: 6, runSpacing: 6, crossAxisAlignment: WrapCrossAlignment.center, children: [
            DmChoiceChip(label: 'Screens', selected: !chat, onDark: true, onTap: () => setState(() => chat = false)),
            DmChoiceChip(label: 'Chat with the agent', selected: chat, onDark: true, onTap: () => setState(() => chat = true)),
            Text(catalogError != null ? '  wardrobe: $catalogError' : '  wardrobe: ${catalogSource ?? '…'}',
                style: DmText.caption.copyWith(color: DmColors.goldLight)),
          ]),
        ),
        Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 760),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 40),
              child: chat
                  ? AgentChat(boAgent: widget.boAgent, examples: widget.examples, user: user, session: session, catalog: catalog)
                  : Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                      for (final s in widget.sections) _section(s),
                      const SizedBox(height: 6),
                      if (busy) const LinearProgressIndicator(),
                      if (result != null) ...[
                        _ResultCard(result: result!, catalog: catalog, api: api),
                        const SizedBox(height: 12),
                        _HowItWorked(result: result!),
                      ],
                    ]),
            ),
          ),
        ),
      ]),
    );
  }

  Widget _section(AgentSection s) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: DmCard(
          padding: const EdgeInsets.all(14),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Expanded(child: Text(s.title, style: DmText.cardTitle)),
              Text(s.tag, style: DmText.caption.copyWith(color: DmColors.bronze, fontWeight: FontWeight.w700)),
            ]),
            if (s.note != null) Text(s.note!, style: DmText.caption),
            const SizedBox(height: 8),
            Wrap(spacing: 6, runSpacing: 6, children: [
              for (final (i, b) in s.buttons.indexed)
                i == 0
                    ? FilledButton(
                        onPressed: busy ? null : () => _tap(b),
                        style: FilledButton.styleFrom(backgroundColor: DmColors.inkDeep),
                        child: Text(running == b.label ? '…' : b.label),
                      )
                    : OutlinedButton(onPressed: busy ? null : () => _tap(b), child: Text(running == b.label ? '…' : b.label)),
            ]),
          ]),
        ),
      );
}

/// Outfits in an agent's data: (item ids, piece names, score).
List<(List<String>, List<String>, double?)> outfitsOf(Json data, {bool withItems = true}) {
  final out = <(List<String>, List<String>, double?)>[];
  for (final k in const ['outfits', 'looks']) {
    for (final o in jsonList(data[k])) {
      if (o['item_ids'] is List) {
        out.add(([for (final i in o['item_ids'] as List) '$i'], [for (final p in (o['pieces'] as List? ?? const [])) '$p'],
            (o['score'] as num?)?.toDouble()));
      }
    }
  }
  if (withItems && data['item_ids'] is List && (data['item_ids'] as List).isNotEmpty) {
    out.add(([for (final i in data['item_ids'] as List) '$i'], [for (final p in (data['pieces'] as List? ?? const [])) '$p'], null));
  }
  return out;
}

class PieceChip extends StatelessWidget {
  const PieceChip({super.key, required this.id, this.name, required this.catalog, required this.api});

  final String id;
  final String? name;
  final Map<String, Json> catalog;
  final DmApi api;

  @override
  Widget build(BuildContext context) {
    final p = catalog[id] ?? const <String, dynamic>{};
    final img = p['image'] as String?;
    return SizedBox(
      width: 92,
      child: Column(children: [
        Container(
          width: 84,
          height: 84,
          decoration: BoxDecoration(color: DmColors.sand, borderRadius: BorderRadius.circular(DmRadius.small)),
          child: img == null || img.isEmpty
              ? const Icon(Icons.checkroom, color: DmColors.bronze)
              : Image.network(api.media(img), fit: BoxFit.contain,
                  errorBuilder: (_, __, ___) => const Icon(Icons.checkroom, color: DmColors.bronze)),
        ),
        const SizedBox(height: 3),
        Text(name ?? '${p['name'] ?? id}', style: DmText.caption, maxLines: 2, textAlign: TextAlign.center, overflow: TextOverflow.ellipsis),
      ]),
    );
  }
}

Widget _pieces(List<String> ids, List<String> names, Map<String, Json> catalog, DmApi api) => SizedBox(
      height: 124,
      child: ListView(scrollDirection: Axis.horizontal, children: [
        for (final (i, id) in ids.indexed)
          Padding(
            padding: const EdgeInsets.only(right: 6),
            child: PieceChip(id: id, name: i < names.length ? names[i] : null, catalog: catalog, api: api),
          ),
      ]),
    );

/// Racem's renderResult: pieces, outfits (proposed / alternative), before -> after for a swap, then key facts.
class _ResultCard extends StatelessWidget {
  const _ResultCard({required this.result, required this.catalog, required this.api});

  final Json result;
  final Map<String, Json> catalog;
  final DmApi api;

  @override
  Widget build(BuildContext context) {
    final data = (result['data'] as Map).cast<String, dynamic>();
    final outs = outfitsOf(data, withItems: false);
    String? idOf(String n) {
      for (final e in catalog.entries) {
        if (e.value['name'] == n) return e.key;
      }
      return null;
    }

    const skip = {'before', 'after', 'outfits', 'looks', 'item_ids', 'pieces', 'next_actions', 'breakdown', 'handled_by'};
    final kv = data.entries.where((e) => !skip.contains(e.key)).take(10).toList();
    return DmCard(
      big: true,
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Container(
            padding: const EdgeInsets.all(9),
            decoration: BoxDecoration(color: DmColors.sandDark, borderRadius: BorderRadius.circular(12)),
            child: Icon(_iconFor('${result['agent']}'), size: 20, color: DmColors.bronze),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(result['button'] != null ? '${result['button']}' : _human('${result['action'] ?? ''}'), style: DmText.title),
              Text('${_agentName('${result['agent'] ?? ''}')} · ${_human('${result['action'] ?? ''}')}', style: DmText.caption),
            ]),
          ),
          if (result['seconds'] != null)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(color: DmColors.sand, borderRadius: BorderRadius.circular(DmRadius.pill)),
              child: Text('${result['seconds']} s', style: DmText.caption.copyWith(fontWeight: FontWeight.w700)),
            ),
        ]),
        const SizedBox(height: 8),
        if (result['error'] != null) Text('${result['error']}', style: DmText.body.copyWith(color: DmColors.warning)),
        if (result['question'] != null) Text('${result['question']}', style: DmText.body),
        if (data['item_ids'] is List && (data['item_ids'] as List).isNotEmpty) ...[
          const SizedBox(height: 8),
          _pieces([for (final i in data['item_ids'] as List) '$i'], [for (final p in (data['pieces'] as List? ?? const [])) '$p'], catalog, api),
        ],
        for (final (k, o) in outs.take(2).indexed) ...[
          const SizedBox(height: 8),
          Text('${k == 0 ? 'proposed' : 'alternative'}${o.$3 != null ? ' · ${(o.$3! * 100).round()} %' : ''}', style: DmText.caption),
          _pieces(o.$1, o.$2, catalog, api),
        ],
        if (data['before'] is List && data['after'] is List) ...[
          const SizedBox(height: 8),
          const Text('before', style: DmText.caption),
          _pieces([for (final n in data['before'] as List) idOf('$n') ?? '$n'], [for (final n in data['before'] as List) '$n'], catalog, api),
          Text('after (${data['slot'] ?? ''} changed)', style: DmText.caption),
          _pieces([for (final n in data['after'] as List) idOf('$n') ?? '$n'], [for (final n in data['after'] as List) '$n'], catalog, api),
        ],
        if (kv.isNotEmpty) ...[
          const SizedBox(height: 10),
          _Facts(entries: kv),
        ] else if (outs.isEmpty && result['error'] == null && result['question'] == null && data['item_ids'] == null)
          const _Empty('Nothing to show yet.'),
      ]),
    );
  }
}

String _short(Object? v) {
  if (v is Map || v is List) {
    final s = v.toString();
    return s.length > 220 ? '${s.substring(0, 220)}…' : s;
  }
  return '$v';
}


String _human(String key) {
  final s = key.split(':').last.split('.').last.replaceAll('_', ' ').trim();
  return s.isEmpty ? s : '${s[0].toUpperCase()}${s.substring(1)}';
}

String _agentName(String agent) => _human(agent.split(':').last.split('.').first);

IconData _iconFor(String agent) {
  final a = agent.toLowerCase();
  if (a.contains('laundry')) return Icons.local_laundry_service_outlined;
  if (a.contains('capsule')) return Icons.inventory_2_outlined;
  if (a.contains('travel')) return Icons.luggage_outlined;
  if (a.contains('forgotten') || a.contains('rotation')) return Icons.history_rounded;
  if (a.contains('style') || a.contains('palette')) return Icons.palette_outlined;
  if (a.contains('gap')) return Icons.add_box_outlined;
  if (a.contains('shop')) return Icons.storefront_outlined;
  if (a.contains('event')) return Icons.event_outlined;
  if (a.contains('declutter')) return Icons.volunteer_activism_outlined;
  return Icons.auto_awesome_outlined;
}

class _Empty extends StatelessWidget {
  const _Empty(this.text);

  final String text;

  @override
  Widget build(BuildContext context) => Container(
        margin: const EdgeInsets.only(top: 6),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(color: DmColors.sand, borderRadius: BorderRadius.circular(DmRadius.small)),
        child: Row(children: [
          const Icon(Icons.check_circle_outline_rounded, size: 18, color: DmColors.success),
          const SizedBox(width: 8),
          Expanded(child: Text(text, style: DmText.body)),
        ]),
      );
}

/// Key facts, readable: numbers as big tiles, maps of numbers as bars, lists as chips, empty values as
/// a friendly line instead of "[]".
class _Facts extends StatelessWidget {
  const _Facts({required this.entries});

  final List<MapEntry<String, dynamic>> entries;

  static const _emptyText = {
    'unavailable': 'Nothing in the laundry: every piece is available.',
    'reminders': 'No reminder.',
    'pieces': 'No piece.',
    'events': 'No event coming.',
    'suggestions': 'No suggestion right now.',
  };

  @override
  Widget build(BuildContext context) {
    final nums = entries.where((e) => e.value is num).toList();
    final maps = entries.where((e) => e.value is Map && (e.value as Map).isNotEmpty).toList();
    final empties = entries.where((e) => e.value == null || (e.value is List && (e.value as List).isEmpty) || (e.value is Map && (e.value as Map).isEmpty) || (e.value is String && (e.value as String).isEmpty)).toList();
    final lists = entries.where((e) => e.value is List && (e.value as List).isNotEmpty).toList();
    final texts = entries.where((e) => e.value is String && (e.value as String).isNotEmpty || e.value is bool).toList();
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      if (nums.isNotEmpty || texts.isNotEmpty)
        Wrap(spacing: 10, runSpacing: 10, children: [
          for (final e in nums) _tile(_human(e.key), _num(e.value as num)),
          for (final e in texts) _tile(_human(e.key), e.value is bool ? (e.value == true ? 'Yes' : 'No') : _human('${e.value}')),
        ]),
      for (final e in maps) ...[
        const SizedBox(height: 14),
        Text(_human(e.key).toUpperCase(), style: DmText.eyebrow),
        const SizedBox(height: 6),
        _map(e.value as Map),
      ],
      for (final e in lists) ...[
        const SizedBox(height: 14),
        Text('${_human(e.key).toUpperCase()} · ${(e.value as List).length}', style: DmText.eyebrow),
        const SizedBox(height: 6),
        Wrap(spacing: 6, runSpacing: 6, children: [
          for (final v in (e.value as List).take(12)) Chip(label: Text(_label(v), style: DmText.caption), visualDensity: VisualDensity.compact),
        ]),
      ],
      for (final e in empties) _Empty(_emptyText[e.key] ?? '${_human(e.key)}: none.'),
    ]);
  }

  static String _num(num v) => v is double && v <= 1 && v > 0 ? '${(v * 100).round()} %' : (v is double ? v.toStringAsFixed(1) : '$v');

  static String _label(Object? v) {
    if (v is Map) {
      for (final k in const ['name', 'title', 'label', 'piece', 'item', 'city', 'shop']) {
        if (v[k] != null) return '${v[k]}';
      }
      return v.values.take(2).join(' · ');
    }
    return '$v';
  }

  Widget _tile(String label, String value) => Container(
        constraints: const BoxConstraints(minWidth: 120),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: DmColors.page,
          borderRadius: BorderRadius.circular(DmRadius.card),
          border: Border.all(color: DmColors.border),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
          Text(value, style: DmText.title.copyWith(fontSize: 22)),
          Text(label, style: DmText.caption),
        ]),
      );

  Widget _map(Map m) {
    final allNum = m.values.every((v) => v is num);
    if (!allNum) {
      return Wrap(spacing: 6, runSpacing: 6, children: [
        for (final e in m.entries) Chip(label: Text('${_human('${e.key}')}: ${_short(e.value)}', style: DmText.caption)),
      ]);
    }
    final maxV = m.values.fold<num>(0, (a, v) => (v as num) > a ? v : a);
    return Column(children: [
      for (final e in m.entries)
        Padding(
          padding: const EdgeInsets.only(bottom: 6),
          child: Row(children: [
            SizedBox(width: 90, child: Text(_human('${e.key}'), style: DmText.caption)),
            Expanded(
              child: ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: LinearProgressIndicator(
                  value: maxV == 0 ? 0 : (e.value as num) / maxV,
                  minHeight: 8,
                  backgroundColor: DmColors.border,
                  valueColor: const AlwaysStoppedAnimation(DmColors.gold),
                ),
              ),
            ),
            SizedBox(width: 40, child: Text('${e.value}', textAlign: TextAlign.right, style: DmText.body.copyWith(fontWeight: FontWeight.w700))),
          ]),
        ),
    ]);
  }
}

/// "Workflow · who calls whom": button -> BO agent -> idea agent -> tools, from the agent steps.
class _HowItWorked extends StatelessWidget {
  const _HowItWorked({required this.result});

  final Json result;

  @override
  Widget build(BuildContext context) {
    final steps = jsonList(result['steps']);
    return DmCard(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('How it worked · who calls whom', style: DmText.cardTitle),
        const SizedBox(height: 8),
        _node(Icons.touch_app_outlined, DmColors.inkDeep, 'Button "${result['button']}"', 'sends an AgentCall (no sentence, so no LLM routing)'),
        Padding(
          padding: const EdgeInsets.only(left: 16),
          child: _node(Icons.hub_outlined, DmColors.bronze, '${result['first'] ?? ''}', 'action ${result['action'] ?? ''}'),
        ),
        Padding(padding: const EdgeInsets.only(left: 32), child: StepTree(steps: steps)),
        const SizedBox(height: 6),
        const Text('The result goes back up the same path as an AgentResult and the screen shows it.', style: DmText.caption),
      ]),
    );
  }
}

Widget _node(IconData icon, Color color, String title, String detail, {String? ms}) => Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Icon(icon, size: 18, color: color),
        const SizedBox(width: 8),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: DmText.body.copyWith(fontWeight: FontWeight.w700, color: DmColors.text)),
            if (detail.isNotEmpty) Text(detail, style: DmText.caption),
          ]),
        ),
        if (ms != null) Text(ms, style: DmText.caption),
      ]),
    );

/// Racem's stepLine: memory · LLM routing · guardrail · tool · agent (with its own sub-steps) · wardrobe · answer.
class StepTree extends StatelessWidget {
  const StepTree({super.key, required this.steps});

  final List<Json> steps;

  @override
  Widget build(BuildContext context) {
    if (steps.isEmpty) return const Text('no step recorded', style: DmText.caption);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      for (final s in steps) ...[
        _line(s),
        if (jsonList(s['sub_steps']).isNotEmpty) Padding(padding: const EdgeInsets.only(left: 16), child: StepTree(steps: jsonList(s['sub_steps']))),
      ],
    ]);
  }

  Widget _line(Json s) {
    final a = '${s['agent'] ?? ''}';
    final ms = s['ms'] is num ? '${((s['ms'] as num) / 1000).toStringAsFixed(1)} s' : null;
    switch (s['step']) {
      case 'memory':
        final p = (s['profile'] as Map?) ?? const {};
        return _node(Icons.memory, DmColors.mutedDark, '$a · memory', '${s['turns'] ?? 0} past messages · likes ${p['likes'] ?? []} · dislikes ${p['dislikes'] ?? []}', ms: ms);
      case 'llm_route':
        return _node(Icons.alt_route, const Color(0xFF6B4FA0), '$a · LLM routing', '→ ${s['decision']}${s['how'] != null ? ' (${s['how']})' : ''}', ms: ms);
      case 'rule_route':
        return _node(Icons.rule, const Color(0xFF6B4FA0), '$a · guardrail', '→ ${s['decision']}', ms: ms);
      case 'llm_answer':
        return _node(Icons.edit_note, const Color(0xFF6B4FA0), '$a · LLM answer', 'reply written from the facts', ms: ms);
      case 'tool':
        return _node(Icons.build_outlined, const Color(0xFF2F6D8A), '$a → tool ${s['to']}.${s['action']}',
            s['ok'] == false ? 'error ${s['error'] ?? ''}' : 'ok', ms: ms);
      case 'agent':
        return _node(Icons.hub_outlined, DmColors.bronze, '$a → agent ${s['to']}${s['action'] != null ? '.${s['action']}' : ''}',
            s['ok'] == false ? 'error' : 'ok', ms: ms);
      case 'wardrobe':
        return _node(Icons.checkroom, const Color(0xFF2F6D8A), '$a · wardrobe (RAG)', '${s['pieces']} pieces · ${s['source']}', ms: ms);
      case 'workflow':
        return _node(Icons.account_tree_outlined, DmColors.bronze, '$a · workflow ${s['action']}', 'done', ms: ms);
      default:
        return _node(Icons.circle, DmColors.muted, '$a · ${s['step']}', '', ms: ms);
    }
  }
}

// ------------------------------------------------------------------ chat with the BO agent (Racem's /bo/demo)
class AgentChat extends ConsumerStatefulWidget {
  const AgentChat({super.key, required this.boAgent, required this.examples, required this.user, required this.session, required this.catalog});

  final String boAgent;
  final List<String> examples;
  final String user;
  final String session;
  final Map<String, Json> catalog;

  @override
  ConsumerState<AgentChat> createState() => _AgentChatState();
}

class _AgentChatState extends ConsumerState<AgentChat> {
  final input = TextEditingController();
  final msgs = <Json>[]; // {me, text, meta, outfits, steps}
  bool busy = false;
  String? llm;

  @override
  void initState() {
    super.initState();
    ref.read(dmApiProvider).get('/stylist/status').then((r) {
      final s = ((r['result'] as Map?) ?? const {}).cast<String, dynamic>();
      if (mounted) setState(() => llm = s['ollama'] == true ? '${s['model']} via Ollama ✓' : 'Ollama not running');
    }).catchError((_) {});
  }

  @override
  void dispose() {
    input.dispose();
    super.dispose();
  }

  Future<void> _send(String text) async {
    final t = text.trim();
    if (t.isEmpty || busy) return;
    input.clear();
    setState(() {
      msgs.add({'me': true, 'text': t});
      busy = true;
    });
    final t0 = DateTime.now();
    try {
      final r = await ref.read(dmApiProvider).post('/bo/chat', {
        'agent': widget.boAgent,
        'user_id': widget.user,
        'session_id': widget.session,
        'message': t,
        'payload': <String, dynamic>{},
      });
      final res = ((r['result'] as Map?) ?? const {}).cast<String, dynamic>();
      final data = ((res['data'] as Map?) ?? const {}).cast<String, dynamic>();
      setState(() => msgs.add({
            'me': false,
            'text': res['reply'] ?? r['question'] ?? res['error'] ?? '(no answer)',
            'meta': '${r['agent']}${data['handled_by'] != null ? ' → ${data['handled_by']}' : ''} · ${res['model'] ?? ''} · '
                '${(DateTime.now().difference(t0).inMilliseconds / 1000).toStringAsFixed(1)} s',
            'outfits': outfitsOf(data),
            'steps': jsonList(res['steps']),
          }));
    } catch (e) {
      setState(() => msgs.add({'me': false, 'text': '⚠ ${apiError(e)}'}));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final api = ref.read(dmApiProvider);
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Text('Local LLM: ${llm ?? '…'}', style: DmText.caption),
      const SizedBox(height: 8),
      if (msgs.isEmpty)
        const DmCard(
          child: Text('Talk to the agent in your own words. Every answer shows its pipeline: memory → routing → '
              'idea agent → tools → answer.', style: DmText.body),
        ),
      for (final m in msgs)
        Align(
          alignment: m['me'] == true ? Alignment.centerRight : Alignment.centerLeft,
          child: Container(
            constraints: const BoxConstraints(maxWidth: 560),
            margin: const EdgeInsets.only(top: 8),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: m['me'] == true ? DmColors.inkDeep : Colors.white,
              borderRadius: BorderRadius.circular(DmRadius.card),
              border: m['me'] == true ? null : Border.all(color: DmColors.border),
            ),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('${m['text']}', style: DmText.body.copyWith(color: m['me'] == true ? Colors.white : DmColors.text, fontSize: 14)),
              if (m['meta'] != null) Text('${m['meta']}', style: DmText.caption),
              for (final o in ((m['outfits'] as List?) ?? const []).cast<(List<String>, List<String>, double?)>().take(3)) ...[
                const SizedBox(height: 6),
                if (o.$3 != null) Text('${(o.$3! * 100).round()} %', style: DmText.caption),
                _pieces(o.$1, o.$2, widget.catalog, api),
              ],
              if (jsonList(m['steps']).isNotEmpty)
                ExpansionTile(
                  tilePadding: EdgeInsets.zero,
                  title: const Text('Agent pipeline', style: DmText.caption),
                  children: [StepTree(steps: jsonList(m['steps']))],
                ),
            ]),
          ),
        ),
      if (busy) const Padding(padding: EdgeInsets.all(8), child: Text('… thinking (local LLM)', style: DmText.caption)),
      const SizedBox(height: 10),
      Wrap(spacing: 6, runSpacing: 6, children: [for (final e in widget.examples) ActionChip(label: Text(e), onPressed: () => _send(e))]),
      const SizedBox(height: 8),
      Row(children: [
        Expanded(child: TextField(controller: input, onSubmitted: _send, decoration: const InputDecoration(hintText: 'Write to the agent…'))),
        const SizedBox(width: 8),
        IconButton.filled(onPressed: busy ? null : () => _send(input.text), icon: const Icon(Icons.send_rounded),
            style: IconButton.styleFrom(backgroundColor: DmColors.inkDeep)),
      ]),
    ]);
  }
}
