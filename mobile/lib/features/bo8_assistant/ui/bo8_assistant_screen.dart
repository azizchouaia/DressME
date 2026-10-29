// Owner: BO8 (Nadhir) — the assistant: ONE chat, the orchestrator picks the agent (POST /chat/message).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/api/dm_api.dart';
import '../../../core/design/dressme_design.dart';
import '../../../core/widgets/dm_widgets.dart';
import '../../../core/widgets/outfit_strip.dart';

class _Msg {
  _Msg.user(this.text)
      : mine = true,
        agent = null,
        actions = const [],
        cards = const [],
        isQuestion = false;
  _Msg.bot(this.text, {this.agent, this.actions = const [], this.cards = const [], this.isQuestion = false}) : mine = false;

  final String text;
  final bool mine;
  final String? agent;
  final List<Json> actions;
  final List<Json> cards;
  final bool isQuestion;
}

const _examples = [
  'What should I wear tomorrow for work?',
  'Should I buy a navy blazer at 120 TND?',
  'Find a white shirt in a shop in Tunis',
  'Show my wardrobe',
  'I love oversize sweaters',
  'Show me the challenges',
];

class ChatScreen extends ConsumerStatefulWidget {
  const ChatScreen({super.key});

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  final _input = TextEditingController();
  final _scroll = ScrollController();
  final _msgs = <_Msg>[];
  late String _session = 'app-${DateTime.now().millisecondsSinceEpoch}';
  bool _busy = false;

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _send(String text) async {
    final t = text.trim();
    if (t.isEmpty || _busy) return;
    _input.clear();
    setState(() {
      _msgs.add(_Msg.user(t));
      _busy = true;
    });
    _down();
    try {
      final r = await ref.read(dmApiProvider).post('/chat/message', {
        'user_id': DemoUsers.wardrobe,
        'session_id': _session,
        'message': t,
      });
      final question = r['question'] as String?;
      setState(() => _msgs.add(_Msg.bot(
            question ?? '${r['reply'] ?? ''}',
            agent: r['last_agent'] as String?,
            actions: jsonList(r['next_actions']),
            cards: jsonList(r['cards']),
            isQuestion: question != null,
          )));
    } catch (e) {
      setState(() => _msgs.add(_Msg.bot('⚠ ${apiError(e)}')));
    } finally {
      if (mounted) setState(() => _busy = false);
      _down();
    }
  }

  void _down() => WidgetsBinding.instance.addPostFrameCallback((_) {
        if (_scroll.hasClients) _scroll.animateTo(_scroll.position.maxScrollExtent, duration: const Duration(milliseconds: 250), curve: Curves.easeOut);
      });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: DmColors.page,
      appBar: AppBar(
        title: const Text('DressMe assistant'),
        actions: [
          IconButton(tooltip: 'Agents', icon: const Icon(Icons.hub_outlined), onPressed: () => _agents(context)),
          IconButton(
            tooltip: 'New conversation',
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () => setState(() {
              _msgs.clear();
              _session = 'app-${DateTime.now().millisecondsSinceEpoch}';
            }),
          ),
        ],
      ),
      body: Column(children: [
        Expanded(
          child: _msgs.isEmpty
              ? ListView(padding: const EdgeInsets.all(20), children: [
                  const DmEmptyState(
                    icon: Icons.chat_bubble_outline_rounded,
                    title: 'Ask me anything about your clothes',
                    message: 'I pick the right agent: stylist, smart buy, local shops, wardrobe, try-on, challenges…',
                  ),
                  const SizedBox(height: 12),
                  Wrap(spacing: 6, runSpacing: 6, alignment: WrapAlignment.center, children: [
                    for (final e in _examples) ActionChip(label: Text(e), onPressed: () => _send(e)),
                  ]),
                ])
              : ListView.builder(
                  controller: _scroll,
                  padding: const EdgeInsets.fromLTRB(12, 12, 12, 12),
                  itemCount: _msgs.length + (_busy ? 1 : 0),
                  itemBuilder: (_, i) => i == _msgs.length ? const _Typing() : _Bubble(msg: _msgs[i], onAction: _send),
                ),
        ),
        SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(12, 6, 12, 10),
            child: Row(children: [
              Expanded(
                child: TextField(
                  controller: _input,
                  textInputAction: TextInputAction.send,
                  onSubmitted: _send,
                  decoration: const InputDecoration(hintText: 'Write in English, Français or Tounsi…'),
                ),
              ),
              const SizedBox(width: 8),
              IconButton.filled(
                onPressed: _busy ? null : () => _send(_input.text),
                icon: const Icon(Icons.send_rounded),
                style: IconButton.styleFrom(backgroundColor: DmColors.inkDeep),
              ),
            ]),
          ),
        ),
      ]),
    );
  }

  void _agents(BuildContext context) {
    final api = ref.read(dmApiProvider);
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (_) => DraggableScrollableSheet(
        expand: false,
        initialChildSize: 0.7,
        builder: (_, c) => FutureBuilder<List<Json>>(
          future: Future.wait([api.get('/chat/status'), api.get('/chat/agents')]),
          builder: (_, snap) {
            if (!snap.hasData) {
              return Center(child: snap.hasError ? Text(apiError(snap.error!)) : const CircularProgressIndicator());
            }
            final status = snap.data![0];
            final llm = (status['llm'] as Map?) ?? const {};
            final ollama = (llm['ollama'] as Map?) ?? const {};
            return ListView(controller: c, padding: const EdgeInsets.all(20), children: [
              const DmSectionHeader(eyebrow: 'Orchestrator (BO8)', title: 'Who can answer'),
              const SizedBox(height: 8),
              Text('Brain: ${llm['model'] ?? '?'} · Ollama ${ollama['ollama'] == true ? 'running ✓' : 'not running ✗'}',
                  style: DmText.body.copyWith(color: ollama['ollama'] == true ? DmColors.success : DmColors.warning)),
              const SizedBox(height: 12),
              for (final a in jsonList(snap.data![1]['agents']))
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: DmCard(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Row(children: [
                        Expanded(child: Text('${a['name']}', style: DmText.cardTitle)),
                        DmPill('${a['owner']} · ${a['module']}'),
                      ]),
                      const SizedBox(height: 4),
                      Text('${a['role']}', style: DmText.body),
                    ]),
                  ),
                ),
            ]);
          },
        ),
      ),
    );
  }
}

class _Bubble extends StatelessWidget {
  const _Bubble({required this.msg, required this.onAction});

  final _Msg msg;
  final void Function(String) onAction;

  @override
  Widget build(BuildContext context) {
    final mine = msg.mine;
    return Align(
      alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 520),
        child: Container(
          margin: const EdgeInsets.only(bottom: 10),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: mine ? DmColors.inkDeep : (msg.isQuestion ? DmColors.warningBg : Colors.white),
            borderRadius: BorderRadius.circular(DmRadius.card),
            border: mine ? null : Border.all(color: msg.isQuestion ? DmColors.gold : DmColors.border),
          ),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            if (msg.agent != null) ...[
              Text('via ${msg.agent}'.toUpperCase(), style: DmText.eyebrow),
              const SizedBox(height: 4),
            ],
            Text(msg.text, style: DmText.body.copyWith(color: mine ? Colors.white : DmColors.text, fontSize: 14)),
            for (final c in msg.cards.take(2)) _CardFacts(card: c),
            if (msg.actions.isNotEmpty) ...[
              const SizedBox(height: 8),
              Wrap(spacing: 6, runSpacing: 6, children: [
                for (final a in msg.actions)
                  if (a['label'] != null)
                    Builder(builder: (context) {
                      // open the right screen (Smart Buy, local shops, avatar, sharing...) or ask in the chat
                      final outfit = [for (final card in msg.cards) ...outfitIdsIn(card)].firstOrNull ?? const <String>[];
                      final route = routeForAction(a, outfit: outfit);
                      return ActionChip(
                        avatar: Icon(route == null ? Icons.chat_bubble_outline : Icons.arrow_forward_rounded, size: 16),
                        label: Text('${a['label']}'),
                        onPressed: () => route == null ? onAction('${a['label']}') : context.go(route),
                      );
                    }),
              ]),
            ],
          ]),
        ),
      ),
    );
  }
}

/// The key facts of an agent's answer (verdict, score, price, outfits, shops) under the reply.
class _CardFacts extends StatelessWidget {
  const _CardFacts({required this.card});

  final Json card;

  @override
  Widget build(BuildContext context) {
    final pills = <String>[
      if (card['verdict'] != null) '${card['verdict']}'.toUpperCase(),
      if (card['score'] != null) 'score ${card['score']}',
      if (card['piece'] != null) '${card['piece']}',
      if (card['results'] is List) '${(card['results'] as List).length} shop results',
      if (card['outfits'] is List) '${(card['outfits'] as List).length} outfits',
      if ((card['result'] as Map?)?['outfits'] is List) '${((card['result'] as Map)['outfits'] as List).length} outfits',
      if ((card['result'] as Map?)?['items'] is List) '${((card['result'] as Map)['items'] as List).length} pieces',
      if (card['challenges'] is List) '${(card['challenges'] as List).length} challenges',
    ];
    final outfits = outfitIdsIn(card);
    if (pills.isEmpty && outfits.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        if (pills.isNotEmpty) Wrap(spacing: 6, runSpacing: 6, children: [for (final p in pills) DmPill(p)]),
        // the outfit itself, with the user's pieces and "See it on me" (BO9)
        for (final ids in outfits.take(1)) ...[
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(color: DmColors.page, borderRadius: BorderRadius.circular(DmRadius.card)),
            child: OutfitStrip(ids: ids, size: 56),
          ),
        ],
      ]),
    );
  }
}

class _Typing extends StatelessWidget {
  const _Typing();

  @override
  Widget build(BuildContext context) => const Align(
        alignment: Alignment.centerLeft,
        child: Padding(
          padding: EdgeInsets.all(8),
          child: Text('The assistant is thinking…', style: DmText.caption),
        ),
      );
}
