// Owner: BO8 (Nadhir) — the assistant: ONE chat, the orchestrator picks the agent (POST /chat/message).
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:speech_to_text/speech_to_text.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/api/dm_api.dart';
import '../../../core/design/dressme_design.dart';
import '../../../core/widgets/dm_widgets.dart';
import '../../../core/widgets/outfit_strip.dart' show outfitIdsIn, routeForAction;
import '../../../core/widgets/dm_motion.dart';
import 'agent_cards.dart';

class _Msg {
  _Msg.user(this.text, {this.photo})
      : mine = true,
        photoLabel = null,
        agent = null,
        actions = const [],
        cards = const [],
        isQuestion = false;
  _Msg.bot(this.text, {this.agent, this.actions = const [], this.cards = const [], this.isQuestion = false, this.photoLabel})
      : mine = false,
        photo = null;

  final String text;
  final bool mine;
  final String? agent;
  final List<Json> actions;
  final List<Json> cards;
  final bool isQuestion;
  final Uint8List? photo; // the user's photo
  final String? photoLabel; // what the assistant read in it
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
  Uint8List? _photo; // attached, sent with the next message
  final _speech = SpeechToText();
  bool _listening = false;
  bool _speechReady = false;

  @override
  void dispose() {
    _speech.stop();
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _pickPhoto(ImageSource source) async {
    final f = await ImagePicker().pickImage(source: source, maxWidth: 900, imageQuality: 85);
    if (f == null) return;
    final bytes = await f.readAsBytes();
    setState(() => _photo = bytes);
  }

  /// Voice: the browser / phone speech recognition writes the words in the box, sent when you stop.
  Future<void> _mic() async {
    if (_listening) {
      await _speech.stop();
      setState(() => _listening = false);
      return;
    }
    _speechReady = _speechReady ||
        await _speech.initialize(onStatus: (s) {
          if ((s == 'done' || s == 'notListening') && mounted) setState(() => _listening = false);
        }, onError: (_) {
          if (mounted) setState(() => _listening = false);
        });
    if (!_speechReady) {
      if (mounted) dmToast(context, 'Voice is not available in this browser (try Chrome) or the microphone is blocked.');
      return;
    }
    setState(() => _listening = true);
    await _speech.listen(
      onResult: (r) {
        setState(() => _input.text = r.recognizedWords);
        if (r.finalResult && r.recognizedWords.trim().isNotEmpty) {
          setState(() => _listening = false);
          _send(r.recognizedWords);
        }
      },
      listenFor: const Duration(seconds: 30),
      pauseFor: const Duration(seconds: 3),
    );
  }

  Future<void> _send(String text) async {
    final t = text.trim();
    final photo = _photo;
    if ((t.isEmpty && photo == null) || _busy) return;
    _input.clear();
    setState(() {
      _msgs.add(_Msg.user(t.isEmpty ? 'What do you think of this piece?' : t, photo: photo));
      _photo = null;
      _busy = true;
    });
    _down();
    try {
      final r = await ref.read(dmApiProvider).post('/chat/message', {
        'user_id': DemoUsers.wardrobe,
        'session_id': _session,
        'message': t,
        if (photo != null) 'image': 'data:image/jpeg;base64,${base64Encode(photo)}',
      });
      final question = r['question'] as String?;
      final seen = (r['photo'] as Map?)?['label'];
      setState(() => _msgs.add(_Msg.bot(
            question ?? '${r['reply'] ?? ''}',
            agent: r['last_agent'] as String?,
            actions: jsonList(r['next_actions']),
            cards: jsonList(r['cards']),
            isQuestion: question != null,
            photoLabel: seen == null ? null : '$seen',
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
                    message: 'Write, speak 🎤 or send a photo 📷. I pick the right agent: stylist, smart buy, local shops, wardrobe, try-on, challenges…',
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
                  itemBuilder: (_, i) => i == _msgs.length
                      ? const _Typing()
                      : DmAppear(key: ValueKey(_msgs[i]), offset: 18, child: _Bubble(msg: _msgs[i], onAction: _send)),
                ),
        ),
        SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(12, 6, 12, 10),
            child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
              if (_photo != null)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Stack(clipBehavior: Clip.none, children: [
                    ClipRRect(borderRadius: BorderRadius.circular(12), child: Image.memory(_photo!, width: 72, height: 72, fit: BoxFit.cover)),
                    Positioned(
                      right: -8,
                      top: -8,
                      child: IconButton.filled(
                        iconSize: 14,
                        constraints: const BoxConstraints(minWidth: 26, minHeight: 26),
                        padding: EdgeInsets.zero,
                        style: IconButton.styleFrom(backgroundColor: DmColors.inkDeep),
                        onPressed: () => setState(() => _photo = null),
                        icon: const Icon(Icons.close_rounded),
                      ),
                    ),
                  ]),
                ),
              Row(children: [
                PopupMenuButton<ImageSource>(
                  tooltip: 'Send a photo of a piece',
                  icon: const Icon(Icons.add_a_photo_outlined, color: DmColors.bronze),
                  onSelected: _pickPhoto,
                  itemBuilder: (_) => const [
                    PopupMenuItem(value: ImageSource.camera, child: Text('Take a photo')),
                    PopupMenuItem(value: ImageSource.gallery, child: Text('From the gallery')),
                  ],
                ),
                Expanded(
                  child: TextField(
                    controller: _input,
                    textInputAction: TextInputAction.send,
                    onSubmitted: _send,
                    decoration: InputDecoration(
                      hintText: _listening
                          ? 'Listening… speak now'
                          : _photo != null
                              ? 'Ask about this piece (or just send)…'
                              : 'Write, speak or send a photo…',
                    ),
                  ),
                ),
                const SizedBox(width: 6),
                AnimatedContainer(
                  duration: const Duration(milliseconds: 250),
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    boxShadow: _listening ? [BoxShadow(color: DmColors.gold.withValues(alpha: .6), blurRadius: 16, spreadRadius: 2)] : const [],
                  ),
                  child: IconButton.filled(
                    tooltip: _listening ? 'Stop' : 'Speak',
                    onPressed: _busy ? null : _mic,
                    icon: Icon(_listening ? Icons.stop_rounded : Icons.mic_none_rounded),
                    style: IconButton.styleFrom(backgroundColor: _listening ? DmColors.gold : DmColors.sandDark, foregroundColor: DmColors.inkDeep),
                  ),
                ),
                const SizedBox(width: 6),
                IconButton.filled(
                  onPressed: _busy ? null : () => _send(_input.text),
                  icon: const Icon(Icons.send_rounded),
                  style: IconButton.styleFrom(backgroundColor: DmColors.inkDeep),
                ),
              ]),
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
            if (msg.photo != null) ...[
              ClipRRect(borderRadius: BorderRadius.circular(10), child: Image.memory(msg.photo!, height: 140, fit: BoxFit.cover)),
              const SizedBox(height: 6),
            ],
            if (msg.photoLabel != null) ...[
              DmPill('📷 I see: ${msg.photoLabel}'),
              const SizedBox(height: 6),
            ],
            Text(msg.text, style: DmText.body.copyWith(color: mine ? Colors.white : DmColors.text, fontSize: 14)),
            for (final c in msg.cards.take(3)) ...[
              _CardFacts(card: c),
              Consumer(builder: (_, ref, __) => AgentCardView(card: c, api: ref.read(dmApiProvider))),
            ],
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
    if (pills.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Wrap(spacing: 6, runSpacing: 6, children: [for (final p in pills) DmPill(p)]),
    );
  }
}

class _Typing extends StatefulWidget {
  const _Typing();

  @override
  State<_Typing> createState() => _TypingState();
}

/// Three bouncing dots while the agents work.
class _TypingState extends State<_Typing> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 900))..repeat();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Align(
        alignment: Alignment.centerLeft,
        child: Container(
          margin: const EdgeInsets.symmetric(vertical: 6),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(DmRadius.card),
            border: Border.all(color: DmColors.border),
          ),
          child: AnimatedBuilder(
            animation: _c,
            builder: (_, __) => Row(mainAxisSize: MainAxisSize.min, children: [
              for (var i = 0; i < 3; i++)
                Transform.translate(
                  offset: Offset(0, _bounce((_c.value - i * .2) % 1.0)),
                  child: Container(
                    width: 7,
                    height: 7,
                    margin: const EdgeInsets.symmetric(horizontal: 2),
                    decoration: const BoxDecoration(color: DmColors.bar, shape: BoxShape.circle),
                  ),
                ),
              const SizedBox(width: 8),
              const Text('The agents are working…', style: DmText.caption),
            ]),
          ),
        ),
      );
}

double _bounce(double p) => p < .5 ? -8 * p : -8 * (1 - p);
