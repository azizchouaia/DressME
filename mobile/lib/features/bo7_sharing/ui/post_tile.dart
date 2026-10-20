// Owner: BO7 · M15 — one challenge post in a feed (card image from M10, like, share).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'share_card_sheet.dart';
import '../data/challenge_models.dart';
import '../logic/challenges_providers.dart';

class PostTile extends ConsumerWidget {
  const PostTile({super.key, required this.post, this.showChallenge = false});
  final ChallengePost post;
  final bool showChallenge;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final repo = ref.read(challengesRepositoryProvider);
    final t = Theme.of(context);
    return Card(
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          ListTile(
            leading: CircleAvatar(child: Text(post.userId.substring(0, 1).toUpperCase())),
            title: Text(post.userId),
            subtitle: Text(showChallenge ? '${post.challengeId} · day ${post.day}' : 'Day ${post.day}'),
          ),
          if (post.cardImageUrl != null)
            AspectRatio(
              aspectRatio: 1080 / 1350,
              child: Image.network(
                repo.absoluteUrl(post.cardImageUrl!),
                fit: BoxFit.cover,
                errorBuilder: (_, __, ___) => const Center(child: Icon(Icons.image_not_supported_outlined)),
              ),
            ),
          if (post.caption != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
              child: Text(post.caption!, style: t.textTheme.bodyMedium),
            ),
          Row(
            children: [
              TextButton.icon(
                onPressed: () => ref.read(challengeActionsProvider(post.challengeId)).like(post.id),
                icon: const Icon(Icons.favorite_border),
                label: Text('${post.likes}'),
              ),
              const Spacer(),
              if (post.shareUrl != null && post.cardImageUrl != null)
                TextButton.icon(
                  onPressed: () => showExistingCardSheet(
                    context,
                    imageUrl: post.cardImageUrl!,
                    shareUrl: post.shareUrl!,
                    caption: post.caption ?? '',
                  ),
                  icon: const Icon(Icons.ios_share),
                  label: const Text('Share'),
                ),
            ],
          ),
        ],
      ),
    );
  }
}
