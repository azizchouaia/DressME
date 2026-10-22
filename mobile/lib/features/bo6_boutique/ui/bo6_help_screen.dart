// Owner: BO6 — "Aider un client": the stylist's workspace after accepting a request (M14 hand-off).
// The stylist reads the request and the client file, picks pieces of the client's wardrobe (M1) and of
// Tunisian shops (M7 search), and sends the look (M14 /looks: M2 score + M10 card); then closes the request.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/design/dressme_design.dart';
import '../../bo6_local_market/data/bo6_local_market_repository.dart';
import '../../bo6_local_market/logic/bo6_local_market_provider.dart'
    show localMarketRepositoryProvider;
import '../../bo6_local_market/ui/bo6_local_market_screen.dart' show formatTnd;
import '../data/bo6_boutique_repository.dart';
import '../logic/bo6_boutique_provider.dart';
import 'bo6_words.dart';

const _pieceEn = {
  'tshirt': 't-shirt',
  'sweater': 'sweater',
  'trousers': 'trousers',
};

/// "White shirt", "Navy jacket": wardrobe codes in plain English.
String _pieceName(WardrobePiece p) {
  final name = _pieceEn[p.subcategory] ?? p.subcategory ?? p.category;
  final colour = p.color?.replaceAll('_', ' ');
  final text = colour == null ? name : '$colour $name';
  return text.isEmpty ? text : '${text[0].toUpperCase()}${text.substring(1)}';
}

class HelpClientScreen extends ConsumerStatefulWidget {
  const HelpClientScreen(
      {super.key, required this.proId, required this.clientId, this.handoffId});

  final String proId;
  final String clientId;
  final String? handoffId; // null when opened from the clients tab

  @override
  ConsumerState<HelpClientScreen> createState() => _HelpClientScreenState();
}

class _HelpClientScreenState extends ConsumerState<HelpClientScreen> {
  final _query = TextEditingController();
  final _budget = TextEditingController();
  final _message = TextEditingController();
  final _items = <String>{}; // wardrobe item ids in the look
  final _products = <String, LocalProduct>{}; // local pieces in the look
  String? _city;
  bool _cityOnly = false;
  bool _prefilled = false;
  bool _searching = false;
  bool _sending = false;
  LocalSearchResult? _found;

  BriefKey get _key => (proId: widget.proId, clientId: widget.clientId);

  @override
  void dispose() {
    _query.dispose();
    _budget.dispose();
    _message.dispose();
    super.dispose();
  }

  /// The local search starts from the client's request: budget and city as said in the chat.
  void _prefill(Handoff h) {
    if (_prefilled) return;
    _prefilled = true;
    _query.text = h.occasion == null ? '' : '${wordEn(h.occasion!)} outfit';
    if (h.budgetTnd != null) _budget.text = h.budgetTnd!.toStringAsFixed(0);
    _city = h.city;
    _cityOnly = h.city != null;
  }

  Future<void> _search() async {
    final query = _query.text.trim();
    if (query.isEmpty) return;
    setState(() => _searching = true);
    try {
      final found = await ref.read(localMarketRepositoryProvider).search(
            query: query,
            city: _cityOnly ? _city : null,
            maxPriceTnd: double.tryParse(_budget.text.replaceAll(',', '.')),
            k: 12,
          );
      setState(() => _found = found);
    } catch (e) {
      _snack(describeError(e));
    } finally {
      if (mounted) setState(() => _searching = false);
    }
  }

  Future<void> _send() async {
    if (_items.isEmpty && _products.isEmpty) {
      _snack('Pick at least one piece (wardrobe or shop).');
      return;
    }
    setState(() => _sending = true);
    try {
      final look = await ref.read(boutiqueRepositoryProvider).sendLook(
            proId: widget.proId,
            clientId: widget.clientId,
            itemIds: _items.toList(),
            productIds: _products.keys.toList(),
            message: _message.text.trim(),
          );
      ref.invalidate(looksProvider(_key));
      ref.invalidate(
          conversationProvider); // the look also appears in the conversation
      setState(() {
        _items.clear();
        _products.clear();
        _message.clear();
      });
      final score = look.score == null
          ? ''
          : ' · compatibility ${(look.score! * 100).round()} %';
      _snack('Look sent to ${widget.clientId}$score.');
    } catch (e) {
      _snack(describeError(e));
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<void> _close() async {
    try {
      await ref
          .read(boutiqueRepositoryProvider)
          .updateHandoff(widget.handoffId!, widget.proId, 'closed');
      ref.invalidate(handoffQueueProvider);
      if (mounted) {
        _snack('Request closed.');
        context.go('/bo6_boutique?tab=1');
      }
    } catch (e) {
      _snack(describeError(e));
    }
  }

  void _snack(String text) {
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final handoff = widget.handoffId == null
        ? null
        : ref.watch(handoffProvider(widget.handoffId!)).valueOrNull;
    if (handoff != null && !_prefilled) {
      // after this frame: changing controllers during build would rebuild the fields mid-build
      WidgetsBinding.instance
          .addPostFrameCallback((_) => setState(() => _prefill(handoff)));
    }
    return Theme(
      data: dressMeTheme(),
      child: Builder(
        builder: (context) => Scaffold(
          body: Column(
            children: [
              _Header(clientId: widget.clientId, handoff: handoff),
              Expanded(
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(16, 16, 16, 120),
                  children: [
                    if (handoff != null) ...[
                      _RequestCard(handoff),
                      const SizedBox(height: 12),
                    ],
                    _BriefCard(_key),
                    const SizedBox(height: 12),
                    _PrivateChat(
                        proId: widget.proId, clientId: widget.clientId),
                    const SizedBox(height: 22),
                    const DmSectionHeader(
                        eyebrow: 'Step 1', title: 'In their wardrobe'),
                    const SizedBox(height: 8),
                    _WardrobePicker(
                      keyIds: _key,
                      selected: _items,
                      onToggle: (id) => setState(() => _items.contains(id)
                          ? _items.remove(id)
                          : _items.add(id)),
                    ),
                    const SizedBox(height: 22),
                    const DmSectionHeader(
                        eyebrow: 'Step 2',
                        title: 'In Tunisian shops'),
                    const SizedBox(height: 8),
                    _searchBar(),
                    const SizedBox(height: 10),
                    if (_searching)
                      const LinearProgressIndicator()
                    else if (_found != null)
                      _results(_found!),
                    const SizedBox(height: 22),
                    const DmSectionHeader(
                        eyebrow: 'Step 3', title: 'The look to send'),
                    const SizedBox(height: 8),
                    _lookTray(),
                    const SizedBox(height: 22),
                    const DmSectionHeader(
                        eyebrow: 'History', title: 'Looks already sent'),
                    const SizedBox(height: 8),
                    _SentLooks(_key),
                  ],
                ),
              ),
            ],
          ),
          bottomNavigationBar: handoff != null && handoff.status == 'accepted'
              ? SafeArea(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
                    child: OutlinedButton.icon(
                      onPressed: _close,
                      icon: const Icon(Icons.check_circle_outline),
                      label: const Text('Close the request (client helped)'),
                    ),
                  ),
                )
              : null,
        ),
      ),
    );
  }

  Widget _searchBar() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: TextField(
                controller: _query,
                textInputAction: TextInputAction.search,
                onSubmitted: (_) => _search(),
                decoration: const InputDecoration(
                  hintText: 'e.g. long green dress, gold sandals…',
                  prefixIcon: Icon(Icons.search, color: DmColors.bronzeDark),
                  isDense: true,
                ),
              ),
            ),
            const SizedBox(width: 8),
            SizedBox(
              width: 110,
              child: TextField(
                controller: _budget,
                keyboardType:
                    const TextInputType.numberWithOptions(decimal: true),
                onSubmitted: (_) => _search(),
                decoration: const InputDecoration(
                    hintText: 'Budget', suffixText: 'TND', isDense: true),
              ),
            ),
            const SizedBox(width: 8),
            FilledButton(onPressed: _search, child: const Text('Search')),
          ],
        ),
        if (_city != null)
          CheckboxListTile(
            value: _cityOnly,
            onChanged: (v) => setState(() => _cityOnly = v ?? false),
            dense: true,
            contentPadding: EdgeInsets.zero,
            controlAffinity: ListTileControlAffinity.leading,
            title:
                Text('Only shops in $_city', style: DmText.body),
          ),
      ],
    );
  }

  Widget _results(LocalSearchResult found) {
    final repo = ref.read(localMarketRepositoryProvider);
    if (found.results.isEmpty) {
      return Text(found.note ?? 'No piece found.', style: DmText.body);
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '${found.totalMatches} piece(s) · tap a piece to add it to the look'
          '${found.note == null ? '' : ' · ${found.note}'}',
          style: DmText.caption,
        ),
        const SizedBox(height: 8),
        SizedBox(
          height: 228,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: found.results.length,
            separatorBuilder: (_, __) => const SizedBox(width: 10),
            itemBuilder: (_, i) {
              final p = found.results[i];
              final picked = _products.containsKey(p.productId);
              return GestureDetector(
                onTap: () => setState(() => picked
                    ? _products.remove(p.productId)
                    : _products[p.productId] = p),
                child: Container(
                  width: 150,
                  decoration: BoxDecoration(
                    color: DmColors.surface,
                    borderRadius: BorderRadius.circular(DmRadius.card),
                    border: Border.all(
                        color: picked ? DmColors.ink : DmColors.border,
                        width: picked ? 2 : 1),
                  ),
                  clipBehavior: Clip.antiAlias,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Stack(
                        children: [
                          Image.network(repo.photoUrl(p),
                              height: 140,
                              width: 150,
                              fit: BoxFit.cover,
                              errorBuilder: (_, __, ___) => const SizedBox(
                                  height: 140,
                                  child: Center(
                                      child: Icon(Icons.checkroom,
                                          color: DmColors.muted)))),
                          if (picked)
                            const Positioned(
                              right: 6,
                              top: 6,
                              child: CircleAvatar(
                                radius: 12,
                                backgroundColor: DmColors.ink,
                                child: Icon(Icons.check,
                                    size: 14, color: Colors.white),
                              ),
                            ),
                        ],
                      ),
                      Padding(
                        padding: const EdgeInsets.all(8),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(p.item,
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                                style: DmText.itemName),
                            const SizedBox(height: 2),
                            Text(
                                '${p.shop}${p.priceTnd == null ? '' : ' · ${formatTnd(p.priceTnd!)}'}',
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: DmText.caption),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      ],
    );
  }

  Widget _lookTray() {
    final pieces = ref.watch(wardrobeProvider(_key)).valueOrNull ?? const [];
    final chosen = pieces.where((p) => _items.contains(p.itemId));
    final total = _products.values
        .map((p) => p.priceTnd ?? 0)
        .fold<double>(0, (a, b) => a + b);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (chosen.isEmpty && _products.isEmpty)
              const Text(
                  'Add pieces from their wardrobe (step 1) and / or from the shops (step 2).',
                  style: DmText.body),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                for (final p in chosen)
                  InputChip(
                    avatar: const Icon(Icons.checkroom, size: 16),
                    label: Text(_pieceName(p)),
                    onDeleted: () => setState(() => _items.remove(p.itemId)),
                  ),
                for (final p in _products.values)
                  InputChip(
                    avatar: const Icon(Icons.storefront_outlined, size: 16),
                    label: Text(
                        '${p.item} · ${p.shop}${p.priceTnd == null ? '' : ' · ${formatTnd(p.priceTnd!)}'}'),
                    onDeleted: () =>
                        setState(() => _products.remove(p.productId)),
                  ),
              ],
            ),
            if (_products.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text('To buy: ${formatTnd(total)}', style: DmText.price),
            ],
            const SizedBox(height: 10),
            TextField(
              controller: _message,
              minLines: 2,
              maxLines: 4,
              decoration: const InputDecoration(
                  hintText:
                      'Your advice to the client (e.g. "With your navy jacket, and these sandals for the wedding")'),
            ),
            const SizedBox(height: 10),
            FilledButton.icon(
              onPressed: _sending ? null : _send,
              icon: const Icon(Icons.send, size: 18),
              label: const Text('Send the look to the client'),
            ),
          ],
        ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.clientId, this.handoff});

  final String clientId;
  final Handoff? handoff;

  @override
  Widget build(BuildContext context) {
    return Container(
      color: DmColors.inkDeep,
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(8, 12, 20, 18),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              IconButton(
                tooltip: 'Back',
                icon: const Icon(Icons.arrow_back, color: Colors.white),
                onPressed: () =>
                    context.go('/bo6_boutique?tab=${handoff == null ? 2 : 1}'),
              ),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('HELP A CLIENT',
                        style: DmText.eyebrow.copyWith(color: DmColors.gold)),
                    const SizedBox(height: 4),
                    Text(clientId,
                        style: DmText.display
                            .copyWith(color: Colors.white, fontSize: 28)),
                    const SizedBox(height: 6),
                    Text(
                      'Read the request and the client file, build a look from their wardrobe '
                      'and pieces from Tunisian shops, then send it.',
                      style: DmText.body.copyWith(
                          color: Colors.white.withValues(alpha: 0.55)),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _RequestCard extends StatelessWidget {
  const _RequestCard(this.h);

  final Handoff h;

  @override
  Widget build(BuildContext context) {
    final facts = [
      if (h.occasion != null) wordEn(h.occasion!),
      if (h.budgetTnd != null) formatTnd(h.budgetTnd!),
      if (h.city != null) h.city!,
    ];
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('THE REQUEST', style: DmText.eyebrow),
            const SizedBox(height: 6),
            Wrap(
                spacing: 6,
                runSpacing: 6,
                children: [for (final f in facts) DmPill(f, dark: true)]),
            const SizedBox(height: 10),
            for (final m in h.messages)
              Align(
                alignment: Alignment.centerLeft,
                child: Container(
                  margin: const EdgeInsets.only(bottom: 6),
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  decoration: BoxDecoration(
                    color: DmColors.sand,
                    borderRadius: BorderRadius.circular(DmRadius.small),
                  ),
                  child: Text(m, style: DmText.body.copyWith(fontSize: 13)),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _BriefCard extends ConsumerWidget {
  const _BriefCard(this.keyIds);

  final BriefKey keyIds;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final brief = ref.watch(clientBriefProvider(keyIds));
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: brief.when(
          loading: () => const LinearProgressIndicator(),
          error: (e, _) => Text(describeError(e), style: DmText.body),
          data: (b) => Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('CLIENT FILE', style: DmText.eyebrow),
              const SizedBox(height: 6),
              for (final line in b.summary)
                Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Text('• $line', style: DmText.body),
                ),
              const SizedBox(height: 4),
              Text(
                'Sources: ${b.sources.entries.map((e) => '${e.key.toUpperCase()} ${e.value == 'real' ? 'real' : 'mock'}').join(' · ')}',
                style: DmText.caption,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _WardrobePicker extends ConsumerWidget {
  const _WardrobePicker(
      {required this.keyIds, required this.selected, required this.onToggle});

  final BriefKey keyIds;
  final Set<String> selected;
  final ValueChanged<String> onToggle;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final pieces = ref.watch(wardrobeProvider(keyIds));
    return pieces.when(
      loading: () => const LinearProgressIndicator(),
      error: (e, _) => Text(describeError(e), style: DmText.body),
      data: (list) => Wrap(
        spacing: 6,
        runSpacing: 6,
        children: [
          for (final p in list)
            FilterChip(
              label: Text('${_pieceName(p)} · worn ${p.wearCount}×'),
              selected: selected.contains(p.itemId),
              onSelected: (_) => onToggle(p.itemId),
            ),
        ],
      ),
    );
  }
}

class _SentLooks extends ConsumerWidget {
  const _SentLooks(this.keyIds);

  final BriefKey keyIds;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final looks = ref.watch(looksProvider(keyIds));
    return looks.when(
      loading: () => const LinearProgressIndicator(),
      error: (e, _) => Text(describeError(e), style: DmText.body),
      data: (list) => list.isEmpty
          ? const Text('No look sent to this client yet.', style: DmText.body)
          : Column(
              children: [
                for (final l in list.reversed)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Card(
                      child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(children: [
                              Expanded(
                                child: Text(
                                  '${l.itemIds.length} piece(s) from their wardrobe · '
                                  '${l.products.length} piece(s) from shops',
                                  style: DmText.itemName,
                                ),
                              ),
                              if (l.score != null)
                                DmPill(
                                    'compatibility ${(l.score! * 100).round()} %',
                                    dark: true),
                            ]),
                            for (final p in l.products)
                              Text(
                                  '· ${p.item} — ${p.shop}${p.priceTnd == null ? '' : ' · ${formatTnd(p.priceTnd!)}'}',
                                  style: DmText.body),
                            if (l.message != null)
                              Text('« ${l.message} »',
                                  style: DmText.body
                                      .copyWith(fontStyle: FontStyle.italic)),
                            Text(
                                'Score: M2 ${l.sources['m2'] == 'real' ? 'real' : 'mock'}',
                                style: DmText.caption),
                          ],
                        ),
                      ),
                    ),
                  ),
              ],
            ),
    );
  }
}

/// Private conversation stylist <-> client (M14 /chat). Only these two people read it; the switch
/// "Client (simulated)" stands for the client's app in the demo.
class _PrivateChat extends ConsumerStatefulWidget {
  const _PrivateChat({required this.proId, required this.clientId});

  final String proId;
  final String clientId;

  @override
  ConsumerState<_PrivateChat> createState() => _PrivateChatState();
}

class _PrivateChatState extends ConsumerState<_PrivateChat> {
  final _text = TextEditingController();
  bool _asClient = false;

  String get _me => _asClient ? widget.clientId : widget.proId;

  ChatKey get _key =>
      (proId: widget.proId, clientId: widget.clientId, reader: _me);

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  Future<void> _run(Future<void> Function() action) async {
    try {
      await action();
      ref.invalidate(conversationProvider);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(describeError(e))));
      }
    }
  }

  Future<void> _send() async {
    final text = _text.text.trim();
    if (text.isEmpty) return;
    _text.clear();
    await _run(() => ref
        .read(boutiqueRepositoryProvider)
        .sendMessage(widget.proId, widget.clientId, _me, text));
  }

  @override
  Widget build(BuildContext context) {
    final chat = ref.watch(conversationProvider(_key));
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.lock_outline,
                    size: 16, color: DmColors.bronze),
                const SizedBox(width: 6),
                const Expanded(
                    child: Text('PRIVATE CONVERSATION', style: DmText.eyebrow)),
                SegmentedButton<bool>(
                  segments: const [
                    ButtonSegment(value: false, label: Text('Stylist')),
                    ButtonSegment(value: true, label: Text('Client (simulated)')),
                  ],
                  selected: {_asClient},
                  showSelectedIcon: false,
                  onSelectionChanged: (v) =>
                      setState(() => _asClient = v.first),
                ),
              ],
            ),
            const SizedBox(height: 4),
            const Text(
                'Only you and this client can read it: never other stylists, '
                'the dashboard or the assistant.',
                style: DmText.caption),
            const SizedBox(height: 10),
            chat.when(
              loading: () => const LinearProgressIndicator(),
              error: (e, _) => Text(describeError(e), style: DmText.body),
              data: (c) => Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (c.messages.isEmpty)
                    const Text('No message yet. Introduce yourself to the client.',
                        style: DmText.body),
                  for (final m in c.messages)
                    _Bubble(m, mine: m.senderId == _me),
                  const SizedBox(height: 8),
                  if (c.canWrite)
                    Row(
                      children: [
                        Expanded(
                          child: TextField(
                            controller: _text,
                            onSubmitted: (_) => _send(),
                            decoration: InputDecoration(
                              isDense: true,
                              hintText: _asClient
                                  ? "Client's message…"
                                  : 'Message to the client…',
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        IconButton.filled(
                          tooltip: 'Send',
                          onPressed: _send,
                          icon: const Icon(Icons.send, size: 18),
                        ),
                      ],
                    )
                  else
                    const Text(
                        'Conversation closed: the client removed access.',
                        style: DmText.body),
                  if (_asClient && c.messages.isNotEmpty)
                    Align(
                      alignment: Alignment.centerLeft,
                      child: TextButton.icon(
                        onPressed: () => _run(() => ref
                            .read(boutiqueRepositoryProvider)
                            .deleteConversation(widget.proId, widget.clientId)),
                        icon: const Icon(Icons.delete_outline, size: 16),
                        label: const Text('Delete the conversation (client)'),
                      ),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Bubble extends StatelessWidget {
  const _Bubble(this.m, {required this.mine});

  final ChatMessage m;
  final bool mine;

  @override
  Widget build(BuildContext context) {
    final at = m.createdAt.toLocal();
    final time =
        '${at.hour.toString().padLeft(2, '0')}:${at.minute.toString().padLeft(2, '0')}';
    return Align(
      alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: const BoxConstraints(maxWidth: 420),
        margin: const EdgeInsets.only(bottom: 6),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: mine ? DmColors.ink : DmColors.sand,
          borderRadius: BorderRadius.circular(DmRadius.small),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (m.lookId != null)
              Row(mainAxisSize: MainAxisSize.min, children: [
                Icon(Icons.checkroom,
                    size: 14,
                    color: mine ? DmColors.goldLight : DmColors.bronze),
                const SizedBox(width: 4),
                Text('Look sent',
                    style: DmText.caption.copyWith(
                        color: mine ? DmColors.goldLight : DmColors.bronze,
                        fontWeight: FontWeight.w700)),
              ]),
            Text(m.text,
                style: DmText.body.copyWith(
                    fontSize: 13, color: mine ? Colors.white : DmColors.text)),
            Text('${m.role == 'stylist' ? 'Stylist' : 'Client'} · $time',
                style: DmText.caption
                    .copyWith(color: mine ? Colors.white60 : DmColors.muted)),
          ],
        ),
      ),
    );
  }
}
