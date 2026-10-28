// Owner: BO6 — "Espace pro": boutique demand dashboard, stylist hand-off queue and clients, through
// M14 (Stylist / boutique mode). Same DressMe design as the local market screen.
import '../../../core/api/dm_api.dart' show DemoUsers;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/design/dressme_design.dart';
import '../../bo6_local_market/data/bo6_local_market_repository.dart'
    show LocalSearchResult, LocalShop, describeError;
import '../../bo6_local_market/logic/bo6_local_market_provider.dart'
    show localMarketRepositoryProvider, localShopsProvider;
import '../data/bo6_boutique_repository.dart';
import '../logic/bo6_boutique_provider.dart';
import 'bo6_words.dart';

String _pct(double v) => '${(v * 100).round()} %';
String _tnd(double v) =>
    '${v.toStringAsFixed(v == v.roundToDouble() ? 0 : 1).replaceAll('.', ',')} TND';

const _status = {
  'queued': 'Waiting',
  'accepted': 'Accepted',
  'declined': 'Declined',
  'closed': 'Closed',
  'not_needed': 'Not needed',
  'no_stylist': 'No stylist free',
  'invited': 'Invited',
  'active': 'Access granted',
  'revoked': 'Access removed',
};
const _reason = {
  'asks_human': 'asks for a stylist',
  'frustration': 'frustration',
  'complex_occasion': 'important occasion',
  'low_confidence': 'the assistant is not sure',
  'long_conversation': 'long conversation',
  'repeated_request': 'repeats the request',
  'user_choice': "client's choice",
};

class BoutiqueScreen extends StatelessWidget {
  const BoutiqueScreen({super.key, this.initialTab = 0});

  /// 0 dashboard, 1 hand-off, 2 clients (route `/bo6_boutique?tab=1`).
  final int initialTab;

  @override
  Widget build(BuildContext context) {
    return Theme(
      data: dressMeTheme(),
      child: DefaultTabController(
        length: 3,
        initialIndex: initialTab.clamp(0, 2),
        child: Builder(
          builder: (context) => const Scaffold(
            body: Column(
              children: [
                _Hero(),
                Expanded(
                  child: TabBarView(
                    children: [_DashboardTab(), _HandoffTab(), _ClientsTab()],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Dark header with the three tabs.
class _Hero extends StatelessWidget {
  const _Hero();

  @override
  Widget build(BuildContext context) {
    final onDark = Colors.white.withValues(alpha: 0.55);
    return Container(
      color: DmColors.inkDeep,
      child: SafeArea(
        bottom: false,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(8, 12, 20, 4),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  IconButton(
                    tooltip: 'Local shops',
                    icon: const Icon(Icons.arrow_back, color: Colors.white),
                    onPressed: () => context.go('/bo6_local_market'),
                  ),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('PRO SPACE',
                            style:
                                DmText.eyebrow.copyWith(color: DmColors.gold)),
                        const SizedBox(height: 4),
                        Text('Shops & stylists',
                            style: DmText.display
                                .copyWith(color: Colors.white, fontSize: 28)),
                        const SizedBox(height: 6),
                        Text(
                            'What clients search for, and the requests the '
                            'assistant passed to a stylist.',
                            style: DmText.body.copyWith(color: onDark)),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const TabBar(
              isScrollable: true,
              tabAlignment: TabAlignment.start,
              labelColor: Colors.white,
              unselectedLabelColor: Colors.white60,
              indicatorColor: DmColors.gold,
              dividerColor: Colors.transparent,
              labelStyle: TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
              tabs: [
                Tab(text: 'Dashboard'),
                Tab(text: 'Stylist hand-off'),
                Tab(text: 'Clients'),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

// ------------------------------------------------------------------ shared small widgets
class _Message extends StatelessWidget {
  const _Message(this.text, {this.icon = Icons.info_outline});

  final String text;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: DmColors.muted, size: 32),
            const SizedBox(height: 10),
            Text(text, textAlign: TextAlign.center, style: DmText.body),
          ],
        ),
      ),
    );
  }
}

class _Loading extends StatelessWidget {
  const _Loading();

  @override
  Widget build(BuildContext context) =>
      const Center(child: CircularProgressIndicator(color: DmColors.bar));
}

/// Horizontal pills to pick one option (account, period, stylist).
class _Picker<T> extends StatelessWidget {
  const _Picker(
      {required this.options, required this.selected, required this.onPick});

  final List<(String, T)> options;
  final T selected;
  final ValueChanged<T> onPick;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 46,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        children: [
          for (final (label, value) in options)
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: ChoiceChip(
                label: Text(label),
                selected: value == selected,
                onSelected: (_) => onPick(value),
              ),
            ),
        ],
      ),
    );
  }
}

class _Card extends StatelessWidget {
  const _Card({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) =>
      Card(child: Padding(padding: const EdgeInsets.all(14), child: child));
}

/// Small bar 0..1 with its label ("sans pièce exacte 36 %").
class _Bar extends StatelessWidget {
  const _Bar({required this.value, required this.label});

  final double value;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: ClipRRect(
            borderRadius: BorderRadius.circular(DmRadius.pill),
            child: LinearProgressIndicator(
                value: value.clamp(0, 1).toDouble(), minHeight: 6),
          ),
        ),
        const SizedBox(width: 8),
        Text(label, style: DmText.caption),
      ],
    );
  }
}

// ------------------------------------------------------------------ tab 1 · dashboard
class _DashboardTab extends ConsumerStatefulWidget {
  const _DashboardTab();

  @override
  ConsumerState<_DashboardTab> createState() => _DashboardTabState();
}

class _DashboardTabState extends ConsumerState<_DashboardTab> {
  static const _market = ''; // DropdownMenu value of "whole market"
  String _shop = _market;
  int _days = 30;

  @override
  Widget build(BuildContext context) {
    final shops = ref.watch(localShopsProvider);
    final dashboard = ref.watch(dashboardProvider(
        (shop: _shop == _market ? null : _shop, days: _days)));
    return Column(
      children: [
        const SizedBox(height: 12),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: shops.when(
            loading: () => const LinearProgressIndicator(),
            error: (e, _) => Text(describeError(e), style: DmText.body),
            // Every shop of the M7 catalogue, with a search field: type "man" -> Manuella.
            data: (list) => LayoutBuilder(
              builder: (context, box) => DropdownMenu<String>(
                width: box.maxWidth,
                initialSelection: _shop,
                enableFilter: true,
                requestFocusOnTap: true,
                menuHeight: 360,
                leadingIcon: const Icon(Icons.storefront_outlined, size: 20),
                label: Text('Shop (${list.length} in the catalogue)'),
                onSelected: (v) => setState(() => _shop = v ?? _market),
                dropdownMenuEntries: [
                  const DropdownMenuEntry(
                      value: _market, label: 'Whole market'),
                  for (final shop in list)
                    DropdownMenuEntry(
                      value: shop.shop,
                      label: shop.shop,
                      trailingIcon: Text(
                          '${shop.city ?? 'online'} · ${shop.products} pieces',
                          style: DmText.caption),
                    ),
                ],
              ),
            ),
          ),
        ),
        const SizedBox(height: 6),
        _Picker<int>(
          options: const [('7 days', 7), ('30 days', 30), ('90 days', 90)],
          selected: _days,
          onPick: (v) => setState(() => _days = v),
        ),
        Expanded(
          child: dashboard.when(
            loading: () => const _Loading(),
            error: (e, _) =>
                _Message(describeError(e), icon: Icons.cloud_off_outlined),
            data: (d) => RefreshIndicator(
              onRefresh: () async => ref.invalidate(dashboardProvider),
              child: _DashboardBody(d),
            ),
          ),
        ),
      ],
    );
  }
}

class _DashboardBody extends StatelessWidget {
  const _DashboardBody(this.d);

  final Dashboard d;

  @override
  Widget build(BuildContext context) {
    if (d.searches == 0) {
      return ListView(children: const [
        _Message('No search in this period. Run the traffic simulator '
            '(python -m modules.m14_stylist_mode.simulate.traffic).'),
      ]);
    }
    final maxOpp = d.unmet.isEmpty
        ? 1.0
        : d.unmet.map((u) => u.opportunity).reduce((a, b) => a > b ? a : b);
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 32),
      children: [
        if (d.simulatedShare > 0)
          Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: DmColors.warningBg,
                borderRadius: BorderRadius.circular(DmRadius.small),
              ),
              child: Text(
                '${_pct(d.simulatedShare)} of the searches come from the simulator '
                '(no real clients yet).',
                style: DmText.body.copyWith(color: DmColors.warning),
              ),
            ),
          ),
        _Kpis(d),
        const SizedBox(height: 14),
        _InsightsCard(shop: d.shop, days: d.periodDays),
        const SizedBox(height: 22),
        DmSectionHeader(
          eyebrow: d.shop == null ? 'Market' : 'Opportunities',
          title: 'Unmet demand',
        ),
        const SizedBox(height: 10),
        if (d.unmet.isEmpty)
          const Text('Nothing to report in this period.', style: DmText.body),
        for (final u in d.unmet)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: _Card(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(u.label, style: DmText.cardTitle),
                  const SizedBox(height: 4),
                  Text(u.hint, style: DmText.body),
                  const SizedBox(height: 8),
                  _Bar(
                      value: u.opportunity / maxOpp,
                      label: 'opportunity ${u.opportunity.round()}'),
                ],
              ),
            ),
          ),
        const SizedBox(height: 18),
        const DmSectionHeader(eyebrow: 'This week', title: 'Trends'),
        const SizedBox(height: 10),
        _Card(
          child: Column(
            children: [
              for (final t in d.trends.take(6))
                ListTile(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(
                    t.rising ? Icons.trending_up : Icons.trending_flat,
                    color: t.rising ? DmColors.success : DmColors.muted,
                  ),
                  title: Text(t.label, style: DmText.itemName),
                  subtitle: Text(
                    '${t.last7Days} searches in 7 days '
                    '(mean ${t.weeklyMeanBefore.toStringAsFixed(1)} / week before)',
                    style: DmText.caption,
                  ),
                  trailing:
                      DmPill('z ${t.z.toStringAsFixed(1)}', dark: t.rising),
                ),
            ],
          ),
        ),
        const SizedBox(height: 18),
        const DmSectionHeader(
            eyebrow: 'Themes', title: 'What clients search for'),
        const SizedBox(height: 10),
        for (final t in d.themes)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: _ThemeCard(t),
          ),
        const SizedBox(height: 18),
        DmSectionHeader(
          eyebrow: 'Prices',
          title: d.shop == null
              ? 'Budgets vs market prices'
              : 'Budgets vs your prices',
        ),
        const SizedBox(height: 10),
        if (d.prices.isEmpty)
          const Text('Not enough budgets given in this period.',
              style: DmText.body),
        for (final p in d.prices)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: _Card(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(child: Text(p.label, style: DmText.itemName)),
                      Text('${p.budgets} budgets', style: DmText.caption),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Median budget ${_tnd(p.demandP50)} '
                    '(${_tnd(p.demandP25)} – ${_tnd(p.demandP75)})'
                    '${p.shopP50 == null ? '' : ' · median price ${d.shop == null ? 'in the market' : 'in your shop'} ${_tnd(p.shopP50!)}'}',
                    style: DmText.body,
                  ),
                  if (p.servedShare != null) ...[
                    const SizedBox(height: 6),
                    _Bar(
                        value: p.servedShare!,
                        label: 'budgets served ${_pct(p.servedShare!)}'),
                  ],
                ],
              ),
            ),
          ),
        const SizedBox(height: 16),
        Text(
          '${d.hiddenGroups} group(s) under 10 searches hidden · '
          '${d.notUnderstood} search(es) not understood. '
          '${d.method['privacy'] ?? ''}',
          style: DmText.caption,
        ),
      ],
    );
  }
}

class _Kpis extends StatelessWidget {
  const _Kpis(this.d);

  final Dashboard d;

  @override
  Widget build(BuildContext context) {
    final f = d.funnel;
    final tiles = <(String, String)>[
      ('Searches', '${d.searches}'),
      if (f != null) ...[
        ('Your pieces shown', '${f.impressions}'),
        ('Pieces opened', '${f.views}'),
        ('Site visits', '${f.clicks}'),
        ('Rank (visits)', f.rank == null ? '–' : '#${f.rank}'),
      ] else
        ('Themes', '${d.themes.length}'),
    ];
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        for (final (label, value) in tiles)
          Container(
            width: 104,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: DmColors.surface,
              borderRadius: BorderRadius.circular(DmRadius.card),
              border: Border.all(color: DmColors.border),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(value, style: DmText.title.copyWith(fontSize: 22)),
                const SizedBox(height: 2),
                Text(label, style: DmText.caption),
              ],
            ),
          ),
      ],
    );
  }
}

class _ThemeCard extends StatelessWidget {
  const _ThemeCard(this.t);

  final DemandTheme t;

  @override
  Widget build(BuildContext context) {
    return _Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(child: Text(t.label, style: DmText.cardTitle)),
              DmPill('${t.searches} · ${_pct(t.share)}'),
            ],
          ),
          const SizedBox(height: 6),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              if (t.medianBudgetTnd != null)
                DmPill('budget ~ ${_tnd(t.medianBudgetTnd!)}'),
              for (final c in t.topCities) DmPill(c),
            ],
          ),
          if (t.examples.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              t.examples.map((e) => '« $e »').join('  '),
              style: DmText.body.copyWith(fontStyle: FontStyle.italic),
            ),
          ],
          const SizedBox(height: 8),
          _Bar(
              value: t.weakAnswerRate,
              label: 'no exact piece ${_pct(t.weakAnswerRate)}'),
        ],
      ),
    );
  }
}

// ------------------------------------------------------------------ tab 2 · hand-off
class _HandoffTab extends ConsumerStatefulWidget {
  const _HandoffTab();

  @override
  ConsumerState<_HandoffTab> createState() => _HandoffTabState();
}

class _HandoffTabState extends ConsumerState<_HandoffTab> {
  String? _stylistId;

  @override
  Widget build(BuildContext context) {
    final stylists = ref.watch(stylistsProvider);
    return stylists.when(
      loading: () => const _Loading(),
      error: (e, _) =>
          _Message(describeError(e), icon: Icons.cloud_off_outlined),
      data: (list) {
        if (list.isEmpty) {
          return const _Message('No stylist. Run '
              'python -m modules.m14_stylist_mode.simulate.pros');
        }
        final selected = _stylistId ?? list.first.proId;
        final me = list.firstWhere((p) => p.proId == selected);
        return ListView(
          padding: const EdgeInsets.only(bottom: 32),
          children: [
            const SizedBox(height: 10),
            _Picker<String>(
              // "Ines (demo) · 1": open hand-offs in each stylist's queue
              options: [
                for (final p in list)
                  (
                    switch (ref
                        .watch(handoffQueueProvider(p.proId))
                        .valueOrNull
                        ?.length) {
                      final n? when n > 0 => '${p.name} · $n',
                      _ => p.name,
                    },
                    p.proId
                  ),
              ],
              selected: selected,
              onPick: (v) => setState(() => _stylistId = v),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
              child: Text(
                '${me.city ?? ''} · ${me.specialities.map(wordEn).join(', ')} · ${me.languages.join(', ')}',
                style: DmText.caption,
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 8),
              // The hand-off goes to the best stylist, not the selected one: show that stylist's queue.
              child: _SimulateChat(onSent: (h) {
                if (h.proId != null) setState(() => _stylistId = h.proId);
              }),
            ),
            const Padding(
              padding: EdgeInsets.fromLTRB(16, 12, 16, 10),
              child: DmSectionHeader(eyebrow: 'My queue', title: 'Requests'),
            ),
            _Queue(stylistId: selected),
          ],
        );
      },
    );
  }
}

class _Queue extends ConsumerWidget {
  const _Queue({required this.stylistId});

  final String stylistId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final queue = ref.watch(handoffQueueProvider(stylistId));
    return queue.when(
      loading: () =>
          const Padding(padding: EdgeInsets.all(24), child: _Loading()),
      error: (e, _) =>
          _Message(describeError(e), icon: Icons.cloud_off_outlined),
      data: (items) => items.isEmpty
          ? const _Message(
              'No request for this stylist. Send a conversation with the '
              'simulator: it goes to the best-suited stylist (speciality, city, language), '
              'and the screen shows it.')
          : Column(
              children: [
                for (final h in items)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                    child: _HandoffCard(h: h, stylistId: stylistId),
                  ),
              ],
            ),
    );
  }
}

class _HandoffCard extends ConsumerWidget {
  const _HandoffCard({required this.h, required this.stylistId});

  final Handoff h;
  final String stylistId;

  String get _helpPath =>
      '/bo6_boutique/help/$stylistId/${h.userId}?handoff=${h.handoffId}';

  Future<void> _set(BuildContext context, WidgetRef ref, String status) async {
    final messenger = ScaffoldMessenger.of(context);
    final router = GoRouter.of(context);
    try {
      final out = await ref
          .read(boutiqueRepositoryProvider)
          .updateHandoff(h.handoffId, stylistId, status);
      ref.invalidate(handoffQueueProvider);
      ref.invalidate(clientLinksProvider);
      if (status == 'accepted') {
        router.go(_helpPath); // accepted: straight to the help page
        return;
      }
      final next = out.candidates
          .where((c) => c.proId == out.proId)
          .map((c) => c.name)
          .firstOrNull;
      messenger.showSnackBar(SnackBar(
        content: Text(status == 'declined'
            ? (next == null
                ? 'Declined: no other stylist available.'
                : 'Declined: passed to $next.')
            : 'Request ${_status[out.status]?.toLowerCase() ?? out.status}.'),
      ));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(describeError(e))));
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final facts = [
      if (h.occasion != null) wordEn(h.occasion!),
      if (h.budgetTnd != null) _tnd(h.budgetTnd!),
      if (h.city != null) h.city!,
    ];
    return _Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(child: Text(h.userId, style: DmText.cardTitle)),
              DmPill(_status[h.status] ?? h.status,
                  dark: h.status == 'accepted'),
            ],
          ),
          const SizedBox(height: 6),
          Wrap(spacing: 6, runSpacing: 6, children: [
            for (final f in facts) DmPill(f),
            if (h.reason != null) DmPill(_reason[h.reason] ?? h.reason!),
          ]),
          const SizedBox(height: 8),
          for (final line in h.summary)
            Padding(
              padding: const EdgeInsets.only(bottom: 3),
              child: Text('• $line', style: DmText.body),
            ),
          const SizedBox(height: 10),
          Row(
            children: [
              if (h.status == 'queued') ...[
                FilledButton(
                    onPressed: () => _set(context, ref, 'accepted'),
                    child: const Text('Accept')),
                const SizedBox(width: 8),
                OutlinedButton(
                    onPressed: () => _set(context, ref, 'declined'),
                    child: const Text('Decline')),
              ],
              if (h.status == 'accepted') ...[
                FilledButton.icon(
                    onPressed: () => context.go(_helpPath),
                    icon: const Icon(Icons.auto_fix_high, size: 18),
                    label: const Text('Help')),
                const SizedBox(width: 8),
                OutlinedButton(
                    onPressed: () => _set(context, ref, 'closed'),
                    child: const Text('Close')),
              ],
            ],
          ),
        ],
      ),
    );
  }
}

/// What the assistant (BO8) does when a chat should go to a human: lets the demo create hand-offs.
class _SimulateChat extends ConsumerStatefulWidget {
  const _SimulateChat({required this.onSent});

  final ValueChanged<Handoff> onSent;

  @override
  ConsumerState<_SimulateChat> createState() => _SimulateChatState();
}

class _SimulateChatState extends ConsumerState<_SimulateChat> {
  final _client = TextEditingController(text: DemoUsers.wardrobe);
  final _chat = TextEditingController(
      text: "n7eb lebsa l 3ers o5ti f Sousse, budget 250 dt\n"
          'ma fhemtnich, n7eb nahki m3a bnadem');
  bool _force = false;
  bool _busy = false;
  Handoff? _last;
  LocalSearchResult?
      _assistant; // what the assistant found by itself (no escalation)

  @override
  void dispose() {
    _client.dispose();
    _chat.dispose();
    super.dispose();
  }

  Future<void> _send({bool force = false}) async {
    final lines = _chat.text
        .split('\n')
        .map((l) => l.trim())
        .where((l) => l.isNotEmpty)
        .toList();
    if (lines.isEmpty) return;
    setState(() => _busy = true);
    try {
      final h = await ref.read(boutiqueRepositoryProvider).createHandoff(
          userId: _client.text.trim().isEmpty ? DemoUsers.wardrobe : _client.text.trim(),
          userMessages: lines,
          force: _force || force);
      // No escalation: the assistant answers alone, here with the M7 search of the last message.
      final found = h.escalate
          ? null
          : await ref
              .read(localMarketRepositoryProvider)
              .search(query: lines.last, k: 3);
      ref.invalidate(handoffQueueProvider);
      setState(() {
        _last = h;
        _assistant = found;
      });
      widget.onSent(h);
      if (mounted && h.proId != null) {
        final to = h.candidates
                .where((c) => c.proId == h.proId)
                .map((c) => c.name)
                .firstOrNull ??
            'a stylist';
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text(h.alreadyOpen
                ? 'Message added to the open request of ${h.userId} with $to '
                    '(${_status[h.status]?.toLowerCase()}): see "Last message".'
                : 'Request sent to $to.')));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(describeError(e))));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final h = _last;
    return _Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('SIMULATE A CLIENT CONVERSATION', style: DmText.eyebrow),
          const SizedBox(height: 4),
          const Text(
              "The client's messages to the assistant, one per line (FR, EN, darija, Arabic).",
              style: DmText.body),
          const SizedBox(height: 10),
          TextField(
            controller: _client,
            decoration:
                const InputDecoration(labelText: 'Client', isDense: true),
          ),
          const SizedBox(height: 8),
          TextField(
            controller: _chat,
            minLines: 2,
            maxLines: 5,
            style: const TextStyle(fontSize: 13),
          ),
          CheckboxListTile(
            value: _force,
            onChanged: (v) => setState(() => _force = v ?? false),
            contentPadding: EdgeInsets.zero,
            dense: true,
            controlAffinity: ListTileControlAffinity.leading,
            title: const Text('The client tapped "Talk to a stylist"',
                style: DmText.body),
          ),
          FilledButton.icon(
            onPressed: _busy ? null : () => _send(),
            icon: _busy
                ? const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(
                        strokeWidth: 2, color: Colors.white))
                : const Icon(Icons.support_agent, size: 18),
            label: const Text('Send to the assistant'),
          ),
          if (h != null) ...[
            const Divider(height: 24),
            Text(
              h.escalate
                  ? 'Escalation${h.byLlm ? ' (AI)' : ''} (${_reason[h.reason] ?? h.reason}, score ${h.score.toStringAsFixed(2)}) '
                      '→ ${_status[h.status] ?? h.status}'
                  : 'No escalation (score ${h.score.toStringAsFixed(2)}): the assistant answers alone.',
              style: DmText.itemName,
            ),
            if (!h.escalate && _assistant != null) ...[
              const SizedBox(height: 6),
              Text(
                _assistant!.results.isEmpty
                    ? 'The assistant found nothing in the shops.'
                    : 'The assistant found ${_assistant!.totalMatches} piece(s) in the shops, e.g.: '
                        '${_assistant!.results.map((p) => '${p.item} (${p.shop}${p.priceTnd == null ? '' : ', ${p.priceTnd!.toStringAsFixed(0)} TND'})').join(' · ')}',
                style: DmText.body,
              ),
              const SizedBox(height: 8),
              OutlinedButton.icon(
                onPressed: _busy ? null : () => _send(force: true),
                icon: const Icon(Icons.support_agent, size: 18),
                label: const Text('The client still wants a stylist'),
              ),
            ],
            for (final (i, c) in h.candidates.indexed)
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Text(
                  '${i + 1}. ${c.name} · ${c.score.toStringAsFixed(2)} · ${c.reasons.join(' · ')}',
                  style: DmText.body,
                ),
              ),
          ],
        ],
      ),
    );
  }
}

// ------------------------------------------------------------------ tab 3 · clients
class _ClientsTab extends ConsumerStatefulWidget {
  const _ClientsTab();

  @override
  ConsumerState<_ClientsTab> createState() => _ClientsTabState();
}

class _ClientsTabState extends ConsumerState<_ClientsTab> {
  String? _proId;
  final _invite = TextEditingController();

  @override
  void dispose() {
    _invite.dispose();
    super.dispose();
  }

  Future<void> _run(Future<void> Function() action) async {
    try {
      await action();
      ref.invalidate(clientLinksProvider);
      ref.invalidate(clientBriefProvider);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(describeError(e))));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final stylists = ref.watch(stylistsProvider).valueOrNull ?? const <Pro>[];
    final boutiques = ref.watch(boutiquesProvider).valueOrNull ?? const <Pro>[];
    // Shops first: their tools (loyalty code, challenges) must be visible
    // without scrolling the picker.
    final pros = [...boutiques, ...stylists];
    if (pros.isEmpty) return const _Loading();
    final selected =
        pros.any((p) => p.proId == _proId) ? _proId! : pros.first.proId;
    final repo = ref.read(boutiqueRepositoryProvider);
    final links = ref.watch(clientLinksProvider(selected));
    return ListView(
      padding: const EdgeInsets.only(bottom: 32),
      children: [
        const SizedBox(height: 10),
        _Picker<String>(
          options: [
            for (final p in pros)
              (p.isBoutique ? '${p.name} · shop' : p.name, p.proId)
          ],
          selected: selected,
          onPick: (v) => setState(() => _proId = v),
        ),
        _ShopAccountPicker(
          boutiques: boutiques,
          onPick: (pro) => setState(() => _proId = pro.proId),
        ),
        if (pros.firstWhere((p) => p.proId == selected).isBoutique)
          _BoutiqueTools(
              key: ValueKey(selected),
              pro: pros.firstWhere((p) => p.proId == selected)),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _invite,
                  decoration: const InputDecoration(
                      hintText: 'Client id (e.g. usr_050)', isDense: true),
                ),
              ),
              const SizedBox(width: 8),
              FilledButton(
                onPressed: () {
                  final id = _invite.text.trim();
                  if (id.isEmpty) return;
                  _run(() => repo.invite(selected, id));
                  _invite.clear();
                },
                child: const Text('Invite'),
              ),
            ],
          ),
        ),
        const Padding(
          padding: EdgeInsets.fromLTRB(16, 4, 16, 6),
          child: Text(
              'Nothing is shared until the client accepts; they can remove access '
              'at any time. The "client" buttons simulate their app.',
              style: DmText.caption),
        ),
        links.when(
          loading: () =>
              const Padding(padding: EdgeInsets.all(24), child: _Loading()),
          error: (e, _) =>
              _Message(describeError(e), icon: Icons.cloud_off_outlined),
          data: (items) => items.isEmpty
              ? const _Message('No client for this account: invite a client id '
                  'above, then accept on the client side.')
              : Column(
                  children: [
                    for (final l in items)
                      Padding(
                        padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                        child: _Card(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(children: [
                                Expanded(
                                    child: Text(l.clientId,
                                        style: DmText.cardTitle)),
                                DmPill(_status[l.status] ?? l.status,
                                    dark: l.status == 'active'),
                              ]),
                              const SizedBox(height: 8),
                              Wrap(spacing: 8, runSpacing: 8, children: [
                                if (l.status == 'invited') ...[
                                  OutlinedButton(
                                      onPressed: () =>
                                          _run(() => repo.consent(l, true)),
                                      child: const Text('Accept (client)')),
                                  OutlinedButton(
                                      onPressed: () =>
                                          _run(() => repo.consent(l, false)),
                                      child: const Text('Decline (client)')),
                                ],
                                if (l.status == 'active') ...[
                                  FilledButton.icon(
                                    onPressed: () => context.go(
                                        '/bo6_boutique/help/$selected/${l.clientId}'),
                                    icon: const Icon(Icons.auto_fix_high,
                                        size: 18),
                                    label: const Text('Help'),
                                  ),
                                  OutlinedButton(
                                    onPressed: () => showModalBottomSheet<void>(
                                      context: context,
                                      isScrollControlled: true,
                                      showDragHandle: true,
                                      builder: (_) => _BriefSheet(
                                          proId: selected,
                                          clientId: l.clientId),
                                    ),
                                    child: const Text('See the file'),
                                  ),
                                  OutlinedButton(
                                      onPressed: () =>
                                          _run(() => repo.revoke(l)),
                                      child:
                                          const Text('Remove access (client)')),
                                ],
                              ]),
                            ],
                          ),
                        ),
                      ),
                  ],
                ),
        ),
      ],
    );
  }
}

class _BriefSheet extends ConsumerWidget {
  const _BriefSheet({required this.proId, required this.clientId});

  final String proId;
  final String clientId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final brief =
        ref.watch(clientBriefProvider((proId: proId, clientId: clientId)));
    return Theme(
      data: dressMeTheme(),
      child: SizedBox(
        height: MediaQuery.of(context).size.height * 0.7,
        child: brief.when(
          loading: () => const _Loading(),
          error: (e, _) => _Message(describeError(e), icon: Icons.lock_outline),
          data: (b) => ListView(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 32),
            children: [
              DmSectionHeader(
                  eyebrow: 'Client file', title: b.archetype ?? b.clientId),
              const SizedBox(height: 12),
              for (final line in b.summary)
                Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: Text('• $line',
                      style: DmText.body.copyWith(fontSize: 13)),
                ),
              const SizedBox(height: 12),
              Text('WARDROBE · ${b.items} PIECES', style: DmText.eyebrow),
              const SizedBox(height: 6),
              Wrap(spacing: 6, runSpacing: 6, children: [
                for (final e in b.perCategory.entries)
                  DmPill('${e.key} ${e.value}'),
                for (final c in b.topColours) DmPill(c, dark: true),
              ]),
              if (b.recentSearches.isNotEmpty) ...[
                const SizedBox(height: 14),
                const Text('SEARCHED IN THE SHOPS', style: DmText.eyebrow),
                const SizedBox(height: 6),
                for (final s in b.recentSearches)
                  Text('« $s »', style: DmText.body),
              ],
              const SizedBox(height: 16),
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

/// Tips for the boutique from the dashboard figures, written by the BO6 LLM (Qwen 2.5 7B, local).
/// Generated on demand only: the model runs on the CPU and takes a few seconds to a minute.
class _InsightsCard extends ConsumerStatefulWidget {
  const _InsightsCard({required this.shop, required this.days});

  final String? shop;
  final int days;

  @override
  ConsumerState<_InsightsCard> createState() => _InsightsCardState();
}

class _InsightsCardState extends ConsumerState<_InsightsCard> {
  Insights? _tips;
  bool _busy = false;
  String? _error;

  @override
  void didUpdateWidget(covariant _InsightsCard old) {
    super.didUpdateWidget(old);
    if (old.shop != widget.shop || old.days != widget.days) {
      setState(() {
        _tips = null;
        _error = null;
      });
    }
  }

  Future<void> _load() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final tips = await ref
          .read(boutiqueRepositoryProvider)
          .insights(shop: widget.shop, days: widget.days);
      setState(() => _tips = tips);
    } catch (e) {
      setState(() => _error = describeError(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = _tips;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: DmColors.ink,
        borderRadius: BorderRadius.circular(DmRadius.card),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.auto_awesome, size: 16, color: DmColors.gold),
              const SizedBox(width: 6),
              Expanded(
                child: Text('AI TIPS',
                    style: DmText.eyebrow.copyWith(color: DmColors.gold)),
              ),
              if (t != null)
                Text(
                    t.source == 'llm'
                        ? 'written by ${t.model}'
                        : 'rules (LLM off)',
                    style: DmText.caption.copyWith(color: Colors.white60)),
            ],
          ),
          const SizedBox(height: 8),
          if (t == null && !_busy) ...[
            const Text(
                'Qwen 2.5 7B (local) turns the figures below into 2-3 tips. '
                'The numbers always come from the dashboard.',
                style: TextStyle(fontSize: 12, color: Colors.white70)),
            const SizedBox(height: 10),
            FilledButton.icon(
              style: FilledButton.styleFrom(
                  backgroundColor: DmColors.gold,
                  foregroundColor: DmColors.inkDeep),
              onPressed: _load,
              icon: const Icon(Icons.auto_awesome, size: 16),
              label: const Text('Generate tips'),
            ),
          ],
          if (_busy)
            const Row(children: [
              SizedBox(
                  width: 14,
                  height: 14,
                  child: CircularProgressIndicator(
                      strokeWidth: 2, color: DmColors.gold)),
              SizedBox(width: 8),
              Text('Qwen is writing the tips (on the CPU, up to a minute)…',
                  style: TextStyle(fontSize: 12, color: Colors.white70)),
            ]),
          if (_error != null)
            Text(_error!,
                style: const TextStyle(fontSize: 12, color: Colors.white70)),
          if (t != null) ...[
            if (t.tips.isEmpty)
              const Text('No tip for this period.',
                  style: TextStyle(fontSize: 12, color: Colors.white70)),
            for (final tip in t.tips)
              Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Text('• $tip',
                    style: const TextStyle(
                        fontSize: 13, color: Colors.white, height: 1.4)),
              ),
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                style: TextButton.styleFrom(foregroundColor: DmColors.gold),
                onPressed: _busy ? null : _load,
                icon: const Icon(Icons.refresh, size: 16),
                label: const Text('Generate again'),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// A boutique account's own tools (BO6): its loyalty code shown on its pieces in the search (Backup 2), and a
/// local brand challenge it sponsors, published on M15 (Backup 5, simulated until BO7 is merged).
/// Any shop of the M7 catalogue: picking one opens its boutique account (created on
/// first use, one account per shop), so its loyalty code and challenges can be managed.
class _ShopAccountPicker extends ConsumerStatefulWidget {
  const _ShopAccountPicker({required this.boutiques, required this.onPick});

  final List<Pro> boutiques;
  final ValueChanged<Pro> onPick;

  @override
  ConsumerState<_ShopAccountPicker> createState() => _ShopAccountPickerState();
}

class _ShopAccountPickerState extends ConsumerState<_ShopAccountPicker> {
  bool _busy = false;

  Future<void> _open(LocalShop shop) async {
    final existing =
        widget.boutiques.where((p) => p.shop == shop.shop).firstOrNull;
    if (existing != null) return widget.onPick(existing);
    setState(() => _busy = true);
    try {
      final pro = await ref
          .read(boutiqueRepositoryProvider)
          .createBoutique(shop.shop, city: shop.city);
      ref.invalidate(boutiquesProvider);
      await ref.read(boutiquesProvider.future);
      widget.onPick(pro);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text('Boutique account opened for ${shop.shop}.')));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(describeError(e))));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final shops = ref.watch(localShopsProvider).valueOrNull;
    if (shops == null) return const SizedBox.shrink();
    final withAccount = {for (final p in widget.boutiques) p.shop};
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
      child: LayoutBuilder(
        builder: (context, box) => DropdownMenu<LocalShop>(
          width: box.maxWidth,
          enabled: !_busy,
          enableFilter: true,
          requestFocusOnTap: true,
          menuHeight: 360,
          leadingIcon: const Icon(Icons.storefront_outlined, size: 20),
          label: Text('Another shop (${shops.length} in the catalogue)'),
          helperText: 'Pick a shop to manage its loyalty code and challenges.',
          onSelected: (s) {
            if (s != null) _open(s);
          },
          dropdownMenuEntries: [
            for (final s in shops)
              DropdownMenuEntry(
                value: s,
                label: s.shop,
                trailingIcon: Text(
                    withAccount.contains(s.shop)
                        ? 'account'
                        : '${s.city ?? 'online'} · ${s.products} pieces',
                    style: DmText.caption),
              ),
          ],
        ),
      ),
    );
  }
}

class _BoutiqueTools extends ConsumerStatefulWidget {
  const _BoutiqueTools({super.key, required this.pro});

  final Pro pro;

  @override
  ConsumerState<_BoutiqueTools> createState() => _BoutiqueToolsState();
}

class _BoutiqueToolsState extends ConsumerState<_BoutiqueTools> {
  final _code = TextEditingController();
  final _pct = TextEditingController(text: '10');
  final _conditions = TextEditingController();
  DateTime? _until;
  Map<String, dynamic>? _current;
  Map<String, dynamic>? _challenge;
  int _challenges = 0;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _code.dispose();
    _pct.dispose();
    _conditions.dispose();
    super.dispose();
  }

  BoutiqueRepository get _repo => ref.read(boutiqueRepositoryProvider);

  Future<void> _load() async {
    final current = await _repo.loyalty(widget.pro.shop!);
    final challenges = await _repo.challenges(widget.pro.proId);
    if (mounted) {
      setState(() {
        _current = current;
        _challenge = challenges.isEmpty ? null : challenges.first;
        _challenges = challenges.length;
      });
    }
  }

  Future<void> _run(Future<void> Function() action) async {
    setState(() => _busy = true);
    try {
      await action();
      await _load();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(describeError(e))));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  /// Same rules as the M14 contract (`Loyalty`), checked here for a readable message.
  void _save() {
    final code = _code.text.trim().toUpperCase();
    final pct = int.tryParse(_pct.text.trim());
    final conditions = _conditions.text.trim();
    final problem = !RegExp(r'^[A-Z0-9-]{3,24}$').hasMatch(code)
        ? 'The code needs 3 to 24 characters: letters, digits or "-" (e.g. MANUELLA10).'
        : (pct == null || pct < 1 || pct > 70)
            ? 'The discount must be between 1 and 70 %.'
            : conditions.length > 120
                ? 'The conditions must fit in 120 characters.'
                : null;
    if (problem != null) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(problem)));
      return;
    }
    _run(() async {
      await _repo.setLoyalty(widget.pro.proId, code, pct!,
          until: _until, conditions: conditions);
      _code.clear();
      _conditions.clear();
      setState(() => _until = null);
    });
  }

  Future<void> _pickUntil() async {
    final today = DateTime.now();
    final day = await showDatePicker(
      context: context,
      initialDate: _until ?? today.add(const Duration(days: 30)),
      firstDate: today,
      lastDate: today.add(const Duration(days: 730)),
      helpText: 'Last day of the code',
    );
    if (day != null) setState(() => _until = day);
  }

  static String _day(DateTime d) => d.toIso8601String().substring(0, 10);

  String _currentText() {
    final c = _current;
    if (c == null) return 'No code: the shop can offer one to DressMe users.';
    return 'Shown on your pieces: ${c['code']} · −${c['discount_pct']} %'
        '${c['until'] == null ? '' : ' · until ${c['until']}'}'
        '${c['conditions'] == null ? '' : ' (${c['conditions']})'}';
  }

  Future<void> _endChallenge(String id) => _run(() async {
        await _repo.endChallenge(id);
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
              content: Text('Challenge ended: the shop can start a new one.')));
        }
      });

  Future<void> _createChallenge() => _run(() async {
        final c = await _repo.createChallenge(widget.pro.proId);
        if (!mounted) return;
        final where = (c['sources'] as Map)['m15'] == 'real'
            ? 'published on M15'
            : 'simulated, M15 not connected yet';
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text('Challenge "${c['title']}" created '
                '(${c['challenge_id']}, $where).')));
      });

  @override
  Widget build(BuildContext context) {
    final c = _challenge;
    final active = c != null && c['status'] == 'active';
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
      child: _Card(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('LOYALTY CODE · ${widget.pro.shop!.toUpperCase()}',
                style: DmText.eyebrow),
            const SizedBox(height: 6),
            Text(_currentText(), style: DmText.body),
            const SizedBox(height: 8),
            Row(children: [
              Expanded(
                child: TextField(
                  controller: _code,
                  textCapitalization: TextCapitalization.characters,
                  decoration: const InputDecoration(
                      hintText: 'New code, e.g. MANUELLA10', isDense: true),
                ),
              ),
              const SizedBox(width: 8),
              SizedBox(
                width: 70,
                child: TextField(
                  controller: _pct,
                  keyboardType: TextInputType.number,
                  decoration:
                      const InputDecoration(suffixText: '%', isDense: true),
                ),
              ),
            ]),
            const SizedBox(height: 8),
            TextField(
              controller: _conditions,
              maxLength: 120,
              decoration: const InputDecoration(
                  hintText: 'Conditions (optional), e.g. from 100 TND',
                  counterText: '',
                  isDense: true),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 4,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                OutlinedButton.icon(
                  icon: const Icon(Icons.event_outlined, size: 18),
                  label: Text(_until == null
                      ? 'No end date'
                      : 'Until ${_day(_until!)}'),
                  onPressed: _busy ? null : _pickUntil,
                ),
                if (_until != null)
                  TextButton(
                    onPressed: () => setState(() => _until = null),
                    child: const Text('No end date'),
                  ),
                FilledButton(
                  onPressed: _busy ? null : _save,
                  child: const Text('Save'),
                ),
                if (_current != null)
                  TextButton(
                    onPressed: _busy
                        ? null
                        : () =>
                            _run(() => _repo.removeLoyalty(widget.pro.proId)),
                    child: const Text('Remove'),
                  ),
              ],
            ),
            const Divider(height: 28),
            const Text('LOCAL BRAND CHALLENGE', style: DmText.eyebrow),
            const SizedBox(height: 6),
            if (c == null)
              const Text(
                  'Sponsor a 7-day challenge: participants wear at least one '
                  'Tunisian piece every day (published on the challenges of BO7).',
                  style: DmText.body)
            else ...[
              Text(c['title'] as String, style: DmText.itemName),
              Text(c['description'] as String, style: DmText.body),
              const SizedBox(height: 6),
              Wrap(spacing: 6, runSpacing: 6, children: [
                if ((c['sources'] as Map)['m15'] != 'real')
                  const DmPill('Simulation: M15 not connected yet'),
                DmPill(active
                    ? 'Active until ${c['ends_on']}'
                    : 'Ended · ${c['ends_on']}'),
                DmPill('Id ${c['challenge_id']}'),
                DmPill('$_challenges sponsored by the shop'),
                DmPill('${c['participants']} participants'),
                for (final p in (c['pieces'] as List).take(4))
                  DmPill((p as Map)['item'] as String),
              ]),
            ],
            const SizedBox(height: 8),
            // One active challenge per shop (M14 answers 409 otherwise).
            if (active)
              OutlinedButton.icon(
                icon: const Icon(Icons.stop_circle_outlined, size: 18),
                label: const Text('End challenge'),
                onPressed: _busy
                    ? null
                    : () => _endChallenge(c['challenge_id'] as String),
              )
            else
              OutlinedButton.icon(
                icon: const Icon(Icons.emoji_events_outlined, size: 18),
                label: const Text('Create a 7-day challenge'),
                onPressed: _busy ? null : _createChallenge,
              ),
          ],
        ),
      ),
    );
  }
}
