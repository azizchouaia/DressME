// Owner: BO7 · M15 — "Communauté": every counted challenge day of everyone, with likes and comments.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/design/dressme_design.dart';
import '../data/bo7_models.dart';
import '../data/bo7_repository.dart';
import '../logic/bo7_providers.dart';
import 'widgets.dart';

class CommunityTab extends ConsumerWidget {
  const CommunityTab({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider);
    return RefreshIndicator(
      onRefresh: () async => ref.invalidate(postsProvider(null)),
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
        children: [
          Bo7Hero(
            eyebrow: 'Communauté · Looks proches du tien',
            title: 'Le fil',
            subtitle: 'Chaque jour de défi validé, de tout le monde. Tu aimes en tant que $user.',
          ),
          const SizedBox(height: 16),
          AsyncBody<List<Post>>(
            value: ref.watch(postsProvider(null)),
            onRetry: () => ref.invalidate(postsProvider(null)),
            builder: (posts) => posts.isEmpty
                ? const Bo7Panel(
                    title: 'Pas encore de publication',
                    child: Text('Ouvre un défi, rejoins-le et valide un jour : il apparaît ici avec sa carte.',
                        style: DmText.body),
                  )
                : LayoutBuilder(
                    builder: (context, box) {
                      final cols = box.maxWidth > 900 ? 3 : (box.maxWidth > 560 ? 2 : 1);
                      final w = (box.maxWidth - 14 * (cols - 1)) / cols;
                      return Wrap(
                        spacing: 14,
                        runSpacing: 14,
                        children: [for (final p in posts) SizedBox(width: w, child: PostCard(post: p))],
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}

/// One post: who, which day, the card made by M10, the caption, like and comments.
class PostCard extends ConsumerStatefulWidget {
  const PostCard({super.key, required this.post});

  final Post post;

  @override
  ConsumerState<PostCard> createState() => _PostCardState();
}

class _PostCardState extends ConsumerState<PostCard> {
  int? _likes;
  bool _liked = false;

  Future<void> _like() async {
    try {
      final n = await ref.read(bo7RepositoryProvider).like(widget.post.id, ref.read(currentUserProvider));
      setState(() {
        _liked = n > (_likes ?? widget.post.likes);
        _likes = n;
      });
    } on Bo7Exception catch (e) {
      if (mounted) showSnack(context, e.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = widget.post;
    final repo = ref.read(bo7RepositoryProvider);
    return Container(
      margin: const EdgeInsets.only(bottom: 4),
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color: DmColors.surface,
        borderRadius: BorderRadius.circular(DmRadius.panel),
        border: Border.all(color: DmColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          ListTile(
            leading: UserAvatar(p.userId),
            title: Text(p.userId, style: DmText.itemName.copyWith(fontSize: 13)),
            subtitle: Text('Jour ${p.day} · ${p.challengeId.replaceFirst('ch_', '')}', style: DmText.caption),
          ),
          if (p.cardImageUrl != null)
            Container(
              color: DmColors.sand,
              constraints: const BoxConstraints(maxHeight: 460),
              child: Image.network(repo.url(p.cardImageUrl!), fit: BoxFit.contain),
            ),
          if (p.caption != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 10, 14, 0),
              child: Text(p.caption!, style: DmText.body.copyWith(color: DmColors.text)),
            ),
          Padding(
            padding: const EdgeInsets.fromLTRB(8, 4, 8, 8),
            child: Row(
              children: [
                TextButton.icon(
                  onPressed: _like,
                  icon: Icon(_liked ? Icons.favorite : Icons.favorite_border, size: 18, color: const Color(0xFFB0573E)),
                  label: Text('${_likes ?? p.likes}'),
                ),
                TextButton.icon(
                  onPressed: () => showModalBottomSheet<void>(
                    context: context,
                    isScrollControlled: true,
                    builder: (_) => Theme(data: dressMeTheme(), child: CommentsSheet(postId: p.id)),
                  ),
                  icon: const Icon(Icons.chat_bubble_outline, size: 17),
                  label: Text('${p.comments} commentaire${p.comments > 1 ? 's' : ''}'),
                ),
                const Spacer(),
                if (p.shareUrl != null)
                  IconButton(
                      icon: const Icon(Icons.ios_share_rounded, size: 18),
                      onPressed: () => openLink(context, p.shareUrl!)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class CommentsSheet extends ConsumerStatefulWidget {
  const CommentsSheet({super.key, required this.postId});

  final String postId;

  @override
  ConsumerState<CommentsSheet> createState() => _CommentsSheetState();
}

class _CommentsSheetState extends ConsumerState<CommentsSheet> {
  final _text = TextEditingController();

  Future<void> _send() async {
    final t = _text.text.trim();
    if (t.isEmpty) return;
    try {
      await ref.read(bo7RepositoryProvider).addComment(widget.postId, ref.read(currentUserProvider), t);
      _text.clear();
      ref.invalidate(commentsProvider(widget.postId));
      ref.invalidate(postsProvider(null));
    } on Bo7Exception catch (e) {
      if (mounted) showSnack(context, e.message); // the M15 moderation can refuse a comment
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.fromLTRB(20, 20, 20, 16 + MediaQuery.of(context).viewInsets.bottom),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const DmSectionHeader(eyebrow: 'Commentaires', title: 'La discussion'),
          const SizedBox(height: 10),
          ConstrainedBox(
            constraints: const BoxConstraints(maxHeight: 320),
            child: AsyncBody<List<Comment>>(
              value: ref.watch(commentsProvider(widget.postId)),
              compact: true,
              builder: (rows) => rows.isEmpty
                  ? const Padding(
                      padding: EdgeInsets.all(12), child: Text('Sois la première à commenter.', style: DmText.body))
                  : ListView(
                      shrinkWrap: true,
                      children: [
                        for (final c in rows)
                          ListTile(
                            dense: true,
                            leading: UserAvatar(c.userId, radius: 14),
                            title: Text(c.userId, style: DmText.itemName),
                            subtitle: Text(c.text, style: DmText.body.copyWith(color: DmColors.text)),
                          ),
                      ],
                    ),
            ),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _text,
                  maxLength: 280,
                  decoration: InputDecoration(
                      hintText: 'Commenter en tant que ${ref.watch(currentUserProvider)}', counterText: ''),
                  onSubmitted: (_) => _send(),
                ),
              ),
              const SizedBox(width: 8),
              FilledButton(onPressed: _send, child: const Text('Publier')),
            ],
          ),
        ],
      ),
    );
  }
}
