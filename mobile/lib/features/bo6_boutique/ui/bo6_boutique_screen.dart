// Owner: BO6 — "Espace pro": boutique demand dashboard, stylist hand-off queue and clients, through
// M14 (Stylist / boutique mode). Same DressMe design as the local market screen.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/design/dressme_design.dart';
import '../../bo6_local_market/data/bo6_local_market_repository.dart'
    show LocalSearchResult, describeError;
import '../../bo6_local_market/logic/bo6_local_market_provider.dart'
    show localMarketRepositoryProvider, localShopsProvider;
import '../data/bo6_boutique_repository.dart';
import '../logic/bo6_boutique_provider.dart';

String _pct(double v) => '${(v * 100).round()} %';
String _tnd(double v) =>
    '${v.toStringAsFixed(v == v.roundToDouble() ? 0 : 1).replaceAll('.', ',')} TND';

const _statusFr = {
  'queued': 'En attente',
  'accepted': 'Acceptée',
  'declined': 'Refusée',
  'closed': 'Close',
  'not_needed': 'Pas nécessaire',
  'no_stylist': 'Aucun styliste libre',
  'invited': 'Invité',
  'active': 'Accès accordé',
  'revoked': 'Accès retiré',
};
const _reasonFr = {
  'asks_human': 'demande un styliste',
  'frustration': 'frustration',
  'complex_occasion': 'occasion importante',
  'low_confidence': "l'assistant n'est pas sûr",
  'long_conversation': 'longue conversation',
  'repeated_request': 'répète sa demande',
  'user_choice': 'choix du client',
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
                    tooltip: 'Boutiques locales',
                    icon: const Icon(Icons.arrow_back, color: Colors.white),
                    onPressed: () => context.go('/bo6_local_market'),
                  ),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('ESPACE PRO',
                            style:
                                DmText.eyebrow.copyWith(color: DmColors.gold)),
                        const SizedBox(height: 4),
                        Text('Boutiques & stylistes',
                            style: DmText.display
                                .copyWith(color: Colors.white, fontSize: 28)),
                        const SizedBox(height: 6),
                        Text(
                            'Ce que cherchent les clients, et les demandes '
                            "passées de l'assistant à un styliste.",
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
                Tab(text: 'Tableau de bord'),
                Tab(text: 'Hand-off styliste'),
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
                label: Text('Boutique (${list.length} dans le catalogue)'),
                onSelected: (v) => setState(() => _shop = v ?? _market),
                dropdownMenuEntries: [
                  const DropdownMenuEntry(
                      value: _market, label: 'Tout le marché'),
                  for (final shop in list)
                    DropdownMenuEntry(
                      value: shop.shop,
                      label: shop.shop,
                      trailingIcon: Text(
                          '${shop.city ?? 'en ligne'} · ${shop.products} articles',
                          style: DmText.caption),
                    ),
                ],
              ),
            ),
          ),
        ),
        const SizedBox(height: 6),
        _Picker<int>(
          options: const [('7 jours', 7), ('30 jours', 30), ('90 jours', 90)],
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
        _Message(
            'Aucune recherche sur la période. Lance le simulateur de trafic '
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
                '${_pct(d.simulatedShare)} des recherches viennent du simulateur '
                '(pas encore de vrais clients).',
                style: DmText.body.copyWith(color: DmColors.warning),
              ),
            ),
          ),
        _Kpis(d),
        const SizedBox(height: 22),
        DmSectionHeader(
          eyebrow: d.shop == null ? 'Marché' : 'Opportunités',
          title: 'Demande non satisfaite',
        ),
        const SizedBox(height: 10),
        if (d.unmet.isEmpty)
          const Text('Rien à signaler sur la période.', style: DmText.body),
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
                      label: 'opportunité ${u.opportunity.round()}'),
                ],
              ),
            ),
          ),
        const SizedBox(height: 18),
        const DmSectionHeader(eyebrow: 'Cette semaine', title: 'Tendances'),
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
                    '${t.last7Days} recherches en 7 jours '
                    '(moyenne ${t.weeklyMeanBefore.toStringAsFixed(1)} / semaine avant)',
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
            eyebrow: 'Thèmes', title: 'Ce que cherchent les clients'),
        const SizedBox(height: 10),
        for (final t in d.themes)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: _ThemeCard(t),
          ),
        const SizedBox(height: 18),
        DmSectionHeader(
          eyebrow: 'Prix',
          title: d.shop == null
              ? 'Budgets vs prix du marché'
              : 'Budgets vs vos prix',
        ),
        const SizedBox(height: 10),
        if (d.prices.isEmpty)
          const Text('Pas assez de budgets donnés sur la période.',
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
                    'Budget médian ${_tnd(p.demandP50)} '
                    '(${_tnd(p.demandP25)} – ${_tnd(p.demandP75)})'
                    '${p.shopP50 == null ? '' : ' · prix médian ${d.shop == null ? 'du marché' : 'chez vous'} ${_tnd(p.shopP50!)}'}',
                    style: DmText.body,
                  ),
                  if (p.servedShare != null) ...[
                    const SizedBox(height: 6),
                    _Bar(
                        value: p.servedShare!,
                        label: 'budgets servis ${_pct(p.servedShare!)}'),
                  ],
                ],
              ),
            ),
          ),
        const SizedBox(height: 16),
        Text(
          '${d.hiddenGroups} groupe(s) de moins de 10 recherches masqué(s) · '
          '${d.notUnderstood} recherche(s) non comprise(s). '
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
      ('Recherches', '${d.searches}'),
      if (f != null) ...[
        ('Vos pièces affichées', '${f.impressions}'),
        ('Pièces ouvertes', '${f.views}'),
        ('Visites du site', '${f.clicks}'),
        ('Rang (visites)', f.rank == null ? '–' : '${f.rank}e'),
      ] else
        ('Thèmes', '${d.themes.length}'),
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
              label: 'sans pièce exacte ${_pct(t.weakAnswerRate)}'),
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
          return const _Message('Aucun styliste. Lance '
              'python -m modules.m14_stylist_mode.simulate.pros');
        }
        final selected = _stylistId ?? list.first.proId;
        final me = list.firstWhere((p) => p.proId == selected);
        return ListView(
          padding: const EdgeInsets.only(bottom: 32),
          children: [
            const SizedBox(height: 10),
            _Picker<String>(
              // "Ines (démo) · 1": open hand-offs in each stylist's queue
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
                '${me.city ?? ''} · ${me.specialities.join(', ')} · ${me.languages.join(', ')}',
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
              child: DmSectionHeader(eyebrow: 'Ma file', title: 'Demandes'),
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
              'Aucune demande pour ce styliste. Envoie une conversation avec le '
              "simulateur : elle part chez le styliste le plus adapté (spécialité, ville, langue), "
              "et l'écran l'affiche.")
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
                ? 'Refusée : aucun autre styliste disponible.'
                : 'Refusée : transmise à $next.')
            : 'Demande ${_statusFr[out.status]?.toLowerCase() ?? out.status}.'),
      ));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(describeError(e))));
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final facts = [
      if (h.occasion != null) h.occasion!,
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
              DmPill(_statusFr[h.status] ?? h.status,
                  dark: h.status == 'accepted'),
            ],
          ),
          const SizedBox(height: 6),
          Wrap(spacing: 6, runSpacing: 6, children: [
            for (final f in facts) DmPill(f),
            if (h.reason != null) DmPill(_reasonFr[h.reason] ?? h.reason!),
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
                    child: const Text('Accepter')),
                const SizedBox(width: 8),
                OutlinedButton(
                    onPressed: () => _set(context, ref, 'declined'),
                    child: const Text('Refuser')),
              ],
              if (h.status == 'accepted') ...[
                FilledButton.icon(
                    onPressed: () => context.go(_helpPath),
                    icon: const Icon(Icons.auto_fix_high, size: 18),
                    label: const Text('Aider')),
                const SizedBox(width: 8),
                OutlinedButton(
                    onPressed: () => _set(context, ref, 'closed'),
                    child: const Text('Clore')),
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
  final _client = TextEditingController(text: 'usr_042');
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
          userId: _client.text.trim().isEmpty ? 'usr_042' : _client.text.trim(),
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
            'un styliste';
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text(h.alreadyOpen
                ? 'Ce client a déjà une demande en cours chez $to '
                    '(${_statusFr[h.status]?.toLowerCase()}) : pas de doublon.'
                : 'Demande envoyée à $to.')));
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
          const Text('SIMULER UNE CONVERSATION CLIENT', style: DmText.eyebrow),
          const SizedBox(height: 4),
          const Text(
              "Messages du client avec l'assistant, un par ligne (FR, EN, darija, arabe).",
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
            title: const Text('Le client a appuyé sur « Parler à un styliste »',
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
            label: const Text("Envoyer à l'assistant"),
          ),
          if (h != null) ...[
            const Divider(height: 24),
            Text(
              h.escalate
                  ? 'Escalade (${_reasonFr[h.reason] ?? h.reason}, score ${h.score.toStringAsFixed(2)}) '
                      '→ ${_statusFr[h.status] ?? h.status}'
                  : "Pas d'escalade (score ${h.score.toStringAsFixed(2)}) : l'assistant répond seul.",
              style: DmText.itemName,
            ),
            if (!h.escalate && _assistant != null) ...[
              const SizedBox(height: 6),
              Text(
                _assistant!.results.isEmpty
                    ? "L'assistant n'a rien trouvé dans les boutiques."
                    : "L'assistant a trouvé ${_assistant!.totalMatches} pièce(s) dans les boutiques, par ex. : "
                        '${_assistant!.results.map((p) => '${p.item} (${p.shop}${p.priceTnd == null ? '' : ', ${p.priceTnd!.toStringAsFixed(0)} TND'})').join(' · ')}',
                style: DmText.body,
              ),
              const SizedBox(height: 8),
              OutlinedButton.icon(
                onPressed: _busy ? null : () => _send(force: true),
                icon: const Icon(Icons.support_agent, size: 18),
                label: const Text('Le client veut quand même un styliste'),
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
    final pros = [...stylists, ...boutiques];
    if (pros.isEmpty) return const _Loading();
    final selected = _proId ?? pros.first.proId;
    final repo = ref.read(boutiqueRepositoryProvider);
    final links = ref.watch(clientLinksProvider(selected));
    return ListView(
      padding: const EdgeInsets.only(bottom: 32),
      children: [
        const SizedBox(height: 10),
        _Picker<String>(
          options: [for (final p in pros) (p.name, p.proId)],
          selected: selected,
          onPick: (v) => setState(() => _proId = v),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _invite,
                  decoration: const InputDecoration(
                      hintText: 'Identifiant client (ex. usr_050)',
                      isDense: true),
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
                child: const Text('Inviter'),
              ),
            ],
          ),
        ),
        const Padding(
          padding: EdgeInsets.fromLTRB(16, 4, 16, 6),
          child: Text(
              "Rien n'est partagé tant que le client n'a pas accepté ; il peut retirer "
              "l'accès à tout moment. Les boutons « client » simulent son app.",
              style: DmText.caption),
        ),
        links.when(
          loading: () =>
              const Padding(padding: EdgeInsets.all(24), child: _Loading()),
          error: (e, _) =>
              _Message(describeError(e), icon: Icons.cloud_off_outlined),
          data: (items) => items.isEmpty
              ? const _Message(
                  "Aucun client pour ce compte : invite un identifiant "
                  'client ci-dessus, puis accepte côté client.')
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
                                DmPill(_statusFr[l.status] ?? l.status,
                                    dark: l.status == 'active'),
                              ]),
                              const SizedBox(height: 8),
                              Wrap(spacing: 8, runSpacing: 8, children: [
                                if (l.status == 'invited') ...[
                                  OutlinedButton(
                                      onPressed: () =>
                                          _run(() => repo.consent(l, true)),
                                      child: const Text('Accepter (client)')),
                                  OutlinedButton(
                                      onPressed: () =>
                                          _run(() => repo.consent(l, false)),
                                      child: const Text('Refuser (client)')),
                                ],
                                if (l.status == 'active') ...[
                                  FilledButton.icon(
                                    onPressed: () => context.go(
                                        '/bo6_boutique/help/$selected/${l.clientId}'),
                                    icon: const Icon(Icons.auto_fix_high,
                                        size: 18),
                                    label: const Text('Aider'),
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
                                    child: const Text('Voir la fiche'),
                                  ),
                                  OutlinedButton(
                                      onPressed: () =>
                                          _run(() => repo.revoke(l)),
                                      child: const Text(
                                          "Retirer l'accès (client)")),
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
                  eyebrow: 'Fiche client', title: b.archetype ?? b.clientId),
              const SizedBox(height: 12),
              for (final line in b.summary)
                Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: Text('• $line',
                      style: DmText.body.copyWith(fontSize: 13)),
                ),
              const SizedBox(height: 12),
              Text('GARDE-ROBE · ${b.items} PIÈCES', style: DmText.eyebrow),
              const SizedBox(height: 6),
              Wrap(spacing: 6, runSpacing: 6, children: [
                for (final e in b.perCategory.entries)
                  DmPill('${e.key} ${e.value}'),
                for (final c in b.topColours) DmPill(c, dark: true),
              ]),
              if (b.recentSearches.isNotEmpty) ...[
                const SizedBox(height: 14),
                const Text('A CHERCHÉ DANS LES BOUTIQUES',
                    style: DmText.eyebrow),
                const SizedBox(height: 6),
                for (final s in b.recentSearches)
                  Text('« $s »', style: DmText.body),
              ],
              const SizedBox(height: 16),
              Text(
                'Sources : ${b.sources.entries.map((e) => '${e.key.toUpperCase()} ${e.value == 'real' ? 'réel' : 'mock'}').join(' · ')}',
                style: DmText.caption,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
