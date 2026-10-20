// Owner: BO7 · M15 — one challenge: rules, join, daily log, progress, leaderboard, posts.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'share_card_sheet.dart';
import '../data/challenge_models.dart';
import '../data/challenges_repository.dart';
import '../logic/challenges_providers.dart';
import 'outfit_picker_sheet.dart';
import 'post_tile.dart';
import 'widgets.dart';

class ChallengeDetailScreen extends ConsumerWidget {
  const ChallengeDetailScreen({super.key, required this.challengeId});
  final String challengeId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final challenge = ref.watch(challengeProvider(challengeId));
    return challenge.when(
      loading: () => const Scaffold(body: Center(child: CircularProgressIndicator())),
      error: (e, _) => Scaffold(appBar: AppBar(), body: Center(child: Text('$e'))),
      data: (c) => DefaultTabController(
        length: 3,
        child: Scaffold(
          appBar: AppBar(
            title: Text(c.title),
            bottom: const TabBar(tabs: [Tab(text: 'My progress'), Tab(text: 'Leaderboard'), Tab(text: 'Posts')]),
          ),
          body: TabBarView(children: [
            _ProgressTab(challenge: c),
            _LeaderboardTab(challengeId: c.id),
            _PostsTab(challengeId: c.id),
          ]),
        ),
      ),
    );
  }
}

class _ProgressTab extends ConsumerStatefulWidget {
  const _ProgressTab({required this.challenge});
  final Challenge challenge;

  @override
  ConsumerState<_ProgressTab> createState() => _ProgressTabState();
}

class _ProgressTabState extends ConsumerState<_ProgressTab> {
  bool _busy = false;
  List<String> _hint = const [];

  Challenge get c => widget.challenge;

  void _snack(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  Future<void> _join() async {
    setState(() => _busy = true);
    try {
      await ref.read(challengeActionsProvider(c.id)).join();
    } on ChallengeException catch (e) {
      _snack(e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _log(int day) async {
    final selection = await showOutfitPicker(context, day: day, preselect: _hint);
    if (selection == null || !mounted) return;
    setState(() => _busy = true);
    try {
      final result = await ref.read(challengeActionsProvider(c.id)).submit(selection.itemIds, caption: selection.caption);
      if (!mounted) return;
      setState(() => _hint = result.suggestion);
      await showModalBottomSheet<void>(
        context: context,
        showDragHandle: true,
        builder: (_) => EntryResultView(result: result),
      );
    } on ChallengeException catch (e) {
      _snack(e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final progress = ref.watch(progressProvider(c.id));
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(c.description, style: t.textTheme.bodyLarge),
        if (c.sponsor != null) ...[
          const SizedBox(height: 8),
          Row(children: [const Icon(Icons.storefront_outlined, size: 16), const SizedBox(width: 6), Text('Sponsored by ${c.sponsor}')]),
        ],
        const SizedBox(height: 16),
        Text('Rules', style: t.textTheme.titleSmall),
        for (final r in c.rules)
          ListTile(
            dense: true,
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.rule, size: 20),
            title: Text(r.description),
          ),
        if (c.feasibility != null) FeasibilityBar(value: c.feasibility!, reason: c.reason),
        const SizedBox(height: 20),
        if (!c.joined)
          FilledButton.icon(
            onPressed: _busy ? null : _join,
            icon: const Icon(Icons.flag_outlined),
            label: Text('Join · ${c.durationDays} days'),
          )
        else
          progress.when(
            loading: () => const LinearProgressIndicator(),
            error: (e, _) => Text('$e'),
            data: (p) => Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                DayStrip(progress: p),
                const SizedBox(height: 16),
                Wrap(spacing: 12, runSpacing: 8, children: [
                  _Stat('${p.validDays}/${p.durationDays}', 'valid days'),
                  _Stat('${p.streak}', 'day streak'),
                  _Stat('${p.points}', 'points'),
                ]),
                if (p.badges.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  Wrap(spacing: 8, children: [for (final b in p.badges) Chip(avatar: const Icon(Icons.emoji_events_outlined, size: 16), label: Text(b))]),
                ],
                const SizedBox(height: 20),
                if (p.finished)
                  const ListTile(leading: Icon(Icons.celebration_outlined), title: Text('Challenge complete'))
                else
                  FilledButton.icon(
                    onPressed: _busy ? null : () => _log(p.nextDay!),
                    icon: _busy
                        ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                        : const Icon(Icons.add_a_photo_outlined),
                    label: Text("Log day ${p.nextDay}'s outfit"),
                  ),
                if (_hint.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Text('Idea for tomorrow is preselected in the picker (${_hint.length} pieces).', style: t.textTheme.bodySmall),
                ],
              ],
            ),
          ),
      ],
    );
  }
}

class _Stat extends StatelessWidget {
  const _Stat(this.value, this.label);
  final String value;
  final String label;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(color: t.colorScheme.surfaceContainerHighest, borderRadius: BorderRadius.circular(12)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(value, style: t.textTheme.titleLarge),
        Text(label, style: t.textTheme.bodySmall),
      ]),
    );
  }
}

/// Shown after "Check my outfit": valid → card + share, invalid → what broke the rules.
class EntryResultView extends ConsumerWidget {
  const EntryResultView({super.key, required this.result});
  final EntryResult result;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = Theme.of(context);
    final post = result.post;
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(24, 0, 24, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Icon(result.valid ? Icons.check_circle : Icons.error_outline,
                size: 48, color: result.valid ? Colors.green.shade600 : t.colorScheme.error),
            const SizedBox(height: 8),
            Text(
              result.valid ? 'Day ${result.day} counts!' : 'Day ${result.day} does not count',
              textAlign: TextAlign.center,
              style: t.textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            for (final v in result.violations)
              ListTile(dense: true, leading: const Icon(Icons.close, size: 18), title: Text(v)),
            if (result.valid)
              Text('${result.progress.validDays} of ${result.progress.durationDays} days done · streak ${result.progress.streak}',
                  textAlign: TextAlign.center),
            const SizedBox(height: 16),
            if (post != null && post.cardImageUrl != null && post.shareUrl != null)
              FilledButton.icon(
                onPressed: () => showExistingCardSheet(
                  context,
                  imageUrl: post.cardImageUrl!,
                  shareUrl: post.shareUrl!,
                  caption: post.caption ?? '',
                ),
                icon: const Icon(Icons.ios_share),
                label: const Text('Share my challenge card'),
              ),
            if (!result.valid)
              FilledButton.tonal(onPressed: () => Navigator.pop(context), child: const Text('Pick other pieces')),
          ],
        ),
      ),
    );
  }
}

class _LeaderboardTab extends ConsumerWidget {
  const _LeaderboardTab({required this.challengeId});
  final String challengeId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final me = ref.watch(currentUserIdProvider);
    final rows = ref.watch(leaderboardProvider(challengeId));
    return RefreshIndicator(
      onRefresh: () async => ref.invalidate(leaderboardProvider(challengeId)),
      child: rows.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ListView(children: [Center(child: Text('$e'))]),
        data: (list) => list.isEmpty
            ? ListView(children: const [SizedBox(height: 80), Center(child: Text('Nobody has joined yet. Be the first!'))])
            : ListView(
                children: [
                  for (final r in list)
                    ListTile(
                      selected: r.userId == me,
                      leading: CircleAvatar(child: Text('${r.rank}')),
                      title: Text(r.userId == me ? '${r.userId} (you)' : r.userId),
                      subtitle: Text('${r.validDays} valid days · ${r.likes} likes'),
                      trailing: Text(r.score.toStringAsFixed(0), style: Theme.of(context).textTheme.titleMedium),
                    ),
                  const Padding(
                    padding: EdgeInsets.all(16),
                    child: Text('Score = 10 per valid day + 5 × average likes (smoothed so one viral post does not win).'),
                  ),
                ],
              ),
      ),
    );
  }
}

class _PostsTab extends ConsumerWidget {
  const _PostsTab({required this.challengeId});
  final String challengeId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final posts = ref.watch(challengePostsProvider(challengeId));
    return RefreshIndicator(
      onRefresh: () async => ref.invalidate(challengePostsProvider(challengeId)),
      child: posts.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ListView(children: [Center(child: Text('$e'))]),
        data: (list) => list.isEmpty
            ? ListView(children: const [SizedBox(height: 80), Center(child: Text('No posts yet.'))])
            : ListView.builder(
                padding: const EdgeInsets.all(12),
                itemCount: list.length,
                itemBuilder: (_, i) => PostTile(post: list[i]),
              ),
      ),
    );
  }
}
