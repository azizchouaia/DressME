// Owner: BO7 · M15 — challenges home: recommended challenges + community feed.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/challenge_models.dart';
import '../logic/challenges_providers.dart';
import 'challenge_detail_screen.dart';
import 'post_tile.dart';
import 'share_screen.dart';
import 'widgets.dart';

class ChallengesScreen extends ConsumerWidget {
  const ChallengesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Challenges'),
          actions: [
            IconButton(
              tooltip: 'Share studio',
              icon: const Icon(Icons.ios_share),
              onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const ShareScreen())),
            ),
          ],
          bottom: const TabBar(tabs: [Tab(text: 'For you'), Tab(text: 'Community')]),
        ),
        body: const TabBarView(children: [_ChallengeList(), _CommunityFeed()]),
      ),
    );
  }
}

class _ChallengeList extends ConsumerWidget {
  const _ChallengeList();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final list = ref.watch(challengesListProvider);
    return RefreshIndicator(
      onRefresh: () async => ref.invalidate(challengesListProvider),
      child: list.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => _ErrorView(message: e.toString(), onRetry: () => ref.invalidate(challengesListProvider)),
        data: (items) => ListView.separated(
          padding: const EdgeInsets.all(16),
          itemCount: items.length,
          separatorBuilder: (_, __) => const SizedBox(height: 12),
          itemBuilder: (_, i) => ChallengeCard(challenge: items[i]),
        ),
      ),
    );
  }
}

class ChallengeCard extends StatelessWidget {
  const ChallengeCard({super.key, required this.challenge});
  final Challenge challenge;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final c = challenge;
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => ChallengeDetailScreen(challengeId: c.id)),
        ),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(children: [
                Expanded(child: Text(c.title, style: t.textTheme.titleMedium)),
                if (c.joined) const Chip(label: Text('Joined'), visualDensity: VisualDensity.compact),
              ]),
              const SizedBox(height: 4),
              Text(c.description, style: t.textTheme.bodyMedium),
              const SizedBox(height: 8),
              Wrap(spacing: 8, children: [
                _Meta(Icons.calendar_today_outlined, '${c.durationDays} days'),
                _Meta(Icons.group_outlined, '${c.participants} joined'),
                if (c.sponsor != null) _Meta(Icons.storefront_outlined, c.sponsor!),
              ]),
              if (c.feasibility != null) ...[
                const SizedBox(height: 12),
                FeasibilityBar(value: c.feasibility!, reason: c.reason),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _Meta extends StatelessWidget {
  const _Meta(this.icon, this.text);
  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) => Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon, size: 14),
        const SizedBox(width: 4),
        Text(text, style: Theme.of(context).textTheme.bodySmall),
      ]);
}

class _CommunityFeed extends ConsumerWidget {
  const _CommunityFeed();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final posts = ref.watch(challengePostsProvider(null));
    return RefreshIndicator(
      onRefresh: () async => ref.invalidate(challengePostsProvider(null)),
      child: posts.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => _ErrorView(message: e.toString(), onRetry: () => ref.invalidate(challengePostsProvider(null))),
        data: (items) => items.isEmpty
            ? ListView(children: const [
                SizedBox(height: 120),
                Center(child: Text('No posts yet. Join a challenge and log your first outfit.')),
              ])
            : ListView.builder(
                padding: const EdgeInsets.all(12),
                itemCount: items.length,
                itemBuilder: (_, i) => PostTile(post: items[i], showChallenge: true),
              ),
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  const _ErrorView({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) => ListView(
        padding: const EdgeInsets.all(32),
        children: [
          const Icon(Icons.cloud_off, size: 40),
          const SizedBox(height: 12),
          Text(message, textAlign: TextAlign.center),
          TextButton(onPressed: onRetry, child: const Text('Try again')),
        ],
      );
}
