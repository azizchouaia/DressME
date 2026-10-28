// Owner: BO7 — the feed of shared looks (/bo7/social/feed): every card shared with M10 and every challenge
// day of M15, with likes, comments (moderated), tagged pieces (M1 + M7), "recreate this look" (M2),
// friends' polls (M6) and give-aways (M1 duplicates, M3). Other teams' modules are mocked until they exist.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/design/dressme_design.dart';
import '../data/bo7_repository.dart';
import '../data/bo7_social_models.dart';
import '../logic/bo7_providers.dart';
import 'widgets.dart';

const kindLabels = {
  'outfit': 'Tenue',
  'board': 'Mon look',
  'tryon': 'Sur mon avatar',
  'recap': 'Bilan du mois',
  'giveaway': 'Je donne',
  'challenge': 'Défi',
  'poll': 'Je l\'achète ?',
  'trip': 'Voyage',
  'style_timeline': 'Mon style',
};

const verdictLabels = {'buy': 'Achète-la', 'think': 'Réfléchis', 'skip': 'Passe ton tour'};

Future<T?> openSheet<T>(BuildContext context, Widget child) => showModalBottomSheet<T>(
      context: context,
      isScrollControlled: true,
      builder: (_) => Theme(data: dressMeTheme(), child: child),
    );

class FeedPostCard extends ConsumerStatefulWidget {
  const FeedPostCard({super.key, required this.post});

  final FeedPost post;

  @override
  ConsumerState<FeedPostCard> createState() => _FeedPostCardState();
}

class _FeedPostCardState extends ConsumerState<FeedPostCard> {
  int? _likes;
  bool? _liked;

  Future<void> _like() async {
    try {
      final n = await ref.read(bo7RepositoryProvider).likePost(widget.post.id, ref.read(currentUserProvider));
      setState(() {
        _liked = n > (_likes ?? widget.post.likes) || (n == (_likes ?? widget.post.likes) && !(_liked ?? false));
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
    final me = ref.watch(currentUserProvider);
    final liked = _liked ?? p.liked;
    return Container(
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
            title: Text(p.userName, style: DmText.itemName.copyWith(fontSize: 13)),
            subtitle: Text(p.title, style: DmText.caption, maxLines: 1, overflow: TextOverflow.ellipsis),
            trailing: DmPill(kindLabels[p.kind] ?? p.kind),
          ),
          if (p.imageUrl != null)
            Container(
              color: DmColors.sand,
              constraints: const BoxConstraints(maxHeight: 440),
              child: Image.network(repo.url(p.imageUrl!), fit: BoxFit.contain),
            ),
          if (p.caption != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 10, 14, 0),
              child: Text(p.caption!, style: DmText.body.copyWith(color: DmColors.text)),
            ),
          if (p.poll != null) Padding(padding: const EdgeInsets.all(12), child: PollBox(poll: p.poll!)),
          if (p.giveaway != null) Padding(padding: const EdgeInsets.all(12), child: GiveawayBox(giveaway: p.giveaway!)),
          Padding(
            padding: const EdgeInsets.fromLTRB(4, 2, 4, 6),
            child: Wrap(
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                TextButton.icon(
                  onPressed: _like,
                  icon: Icon(liked ? Icons.favorite : Icons.favorite_border, size: 18, color: const Color(0xFFB0573E)),
                  label: Text('${_likes ?? p.likes}'),
                ),
                TextButton.icon(
                  onPressed: () => openSheet<void>(context, FeedCommentsSheet(postId: p.id)),
                  icon: const Icon(Icons.chat_bubble_outline, size: 17),
                  label: Text('${p.comments}'),
                ),
                if (p.itemIds.isNotEmpty && p.source == 'share')
                  TextButton.icon(
                    onPressed: () => openSheet<void>(
                        context, PiecesSheet(ownerId: p.userId, ownerName: p.userName, itemIds: p.itemIds)),
                    icon: const Icon(Icons.sell_outlined, size: 17),
                    label: Text('${p.itemIds.length} pièces'),
                  ),
                if (p.itemIds.isNotEmpty && p.source == 'share' && p.userId != me)
                  TextButton.icon(
                    onPressed: () => openSheet<void>(context, RecreateSheet(postId: p.id, ownerName: p.userName)),
                    icon: const Icon(Icons.autorenew_rounded, size: 17),
                    label: const Text('Recréer'),
                  ),
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

/// "Should I buy this?": the M6 verdict, then friends vote (the author sees the results).
class PollBox extends ConsumerStatefulWidget {
  const PollBox({super.key, required this.poll});

  final Poll poll;

  @override
  ConsumerState<PollBox> createState() => _PollBoxState();
}

class _PollBoxState extends ConsumerState<PollBox> {
  Poll? _poll;

  Future<void> _vote(String choice) async {
    try {
      final p = await ref.read(bo7RepositoryProvider).vote(widget.poll.id, ref.read(currentUserProvider), choice);
      setState(() => _poll = p);
    } on Bo7Exception catch (e) {
      if (mounted) showSnack(context, e.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = _poll ?? widget.poll;
    final mine = p.userId == ref.watch(currentUserProvider);
    final color =
        switch (p.verdict) { 'buy' => DmColors.success, 'skip' => const Color(0xFFB0573E), _ => DmColors.warning };
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: DmColors.sand, borderRadius: BorderRadius.circular(DmRadius.card)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Icon(Icons.auto_awesome, size: 16, color: color),
              const SizedBox(width: 6),
              Expanded(
                child: Text('Avis IA (M6) : ${verdictLabels[p.verdict] ?? p.verdict}',
                    style: DmText.itemName.copyWith(color: color)),
              ),
              Text('${(p.score * 100).round()} / 100', style: DmText.caption),
            ],
          ),
          Text(
            p.similar > 0
                ? 'Tu as déjà ${p.similar} pièce(s) qui y ressemblent.'
                : 'Elle crée ${p.newOutfits} nouvelle(s) tenue(s) avec ta garde-robe.',
            style: DmText.caption,
          ),
          const SizedBox(height: 10),
          if (!mine && p.myVote == null)
            Row(
              children: [
                Expanded(child: FilledButton(onPressed: () => _vote('yes'), child: const Text('Oui, achète'))),
                const SizedBox(width: 8),
                Expanded(child: OutlinedButton(onPressed: () => _vote('no'), child: const Text('Non'))),
              ],
            )
          else ...[
            ClipRRect(
              borderRadius: BorderRadius.circular(6),
              child: LinearProgressIndicator(value: p.total == 0 ? 0 : p.yesShare, minHeight: 8),
            ),
            const SizedBox(height: 4),
            Text(
              p.total == 0
                  ? 'Pas encore de vote : partage le lien à tes amis.'
                  : '${(p.yesShare * 100).round()} % oui · ${p.total} vote(s)'
                      '${p.myVote != null ? ' · ton vote : ${p.myVote == 'yes' ? 'oui' : 'non'}' : ''}',
              style: DmText.caption,
            ),
            if (!mine)
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton(
                  onPressed: () => _vote(p.myVote == 'yes' ? 'no' : 'yes'),
                  child: const Text('Changer mon vote'),
                ),
              ),
          ],
        ],
      ),
    );
  }
}

/// A give-away: friends ask for the piece, the owner chooses who gets it.
class GiveawayBox extends ConsumerStatefulWidget {
  const GiveawayBox({super.key, required this.giveaway});

  final Giveaway giveaway;

  @override
  ConsumerState<GiveawayBox> createState() => _GiveawayBoxState();
}

class _GiveawayBoxState extends ConsumerState<GiveawayBox> {
  Giveaway? _g;

  Future<void> _run(Future<Giveaway> Function() f) async {
    try {
      final g = await f();
      setState(() => _g = g);
    } on Bo7Exception catch (e) {
      if (mounted) showSnack(context, e.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    final g = _g ?? widget.giveaway;
    final me = ref.watch(currentUserProvider);
    final repo = ref.read(bo7RepositoryProvider);
    final details = [if (g.size != null) 'taille ${g.size}', g.condition, if (g.city != null) g.city!].join(' · ');
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: DmColors.ecoBg, borderRadius: BorderRadius.circular(DmRadius.card)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              const Icon(Icons.volunteer_activism_outlined, size: 16, color: DmColors.eco),
              const SizedBox(width: 6),
              Expanded(child: Text(g.open ? 'À donner · $details' : 'Donnée à ${g.givenTo}', style: DmText.itemName)),
            ],
          ),
          const SizedBox(height: 6),
          if (g.userId == me) ...[
            if (g.requests.isEmpty) const Text('Personne ne l\'a encore demandée.', style: DmText.caption),
            for (final r in g.requests)
              ListTile(
                dense: true,
                contentPadding: EdgeInsets.zero,
                leading: UserAvatar(r.userId, radius: 13),
                title: Text(r.userName, style: DmText.itemName),
                subtitle: r.message == null ? null : Text(r.message!, style: DmText.caption),
                trailing: g.open
                    ? TextButton(
                        onPressed: () => _run(() => repo.give(g.id, me, r.userId)), child: const Text('Lui donner'))
                    : (g.givenTo == r.userId ? const Icon(Icons.check_circle, color: DmColors.eco) : null),
              ),
          ] else if (g.open)
            g.requested
                ? const Text('Tu l\'as demandée : la propriétaire choisit.', style: DmText.caption)
                : FilledButton.icon(
                    onPressed: () => _run(() => repo.requestGiveaway(g.id, me, message: 'Je la veux bien !')),
                    icon: const Icon(Icons.pan_tool_alt_outlined, size: 17),
                    label: const Text('Je la veux'),
                  ),
        ],
      ),
    );
  }
}

class FeedCommentsSheet extends ConsumerStatefulWidget {
  const FeedCommentsSheet({super.key, required this.postId});

  final String postId;

  @override
  ConsumerState<FeedCommentsSheet> createState() => _FeedCommentsSheetState();
}

class _FeedCommentsSheetState extends ConsumerState<FeedCommentsSheet> {
  final _text = TextEditingController();

  Future<void> _send() async {
    final t = _text.text.trim();
    if (t.isEmpty) return;
    try {
      await ref.read(bo7RepositoryProvider).commentPost(widget.postId, ref.read(currentUserProvider), t);
      _text.clear();
      ref.invalidate(feedCommentsProvider(widget.postId));
      refreshFeed(ref);
    } on Bo7Exception catch (e) {
      if (mounted) showSnack(context, e.message); // moderation can refuse a comment
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
            child: AsyncBody<List<FeedComment>>(
              value: ref.watch(feedCommentsProvider(widget.postId)),
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
                            title: Text(c.userName, style: DmText.itemName),
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
                  decoration: const InputDecoration(hintText: 'Un mot gentil…', counterText: ''),
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

/// Tagged pieces of a look: tap a tag to see the piece (M1) and where to find something close in Tunisia (M7).
class PiecesSheet extends ConsumerWidget {
  const PiecesSheet({super.key, required this.ownerId, required this.ownerName, required this.itemIds});

  final String ownerId;
  final String ownerName;
  final List<String> itemIds;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final future = ref.read(bo7RepositoryProvider).taggedPieces(ownerId, itemIds);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          DmSectionHeader(eyebrow: 'Pièces taguées · M1 + M7', title: 'Le look de $ownerName'),
          const SizedBox(height: 10),
          ConstrainedBox(
            constraints: BoxConstraints(maxHeight: MediaQuery.of(context).size.height * 0.6),
            child: FutureBuilder<List<TaggedPiece>>(
              future: future,
              builder: (context, snap) {
                if (snap.hasError) return Text(snap.error.toString(), style: DmText.body);
                if (!snap.hasData) return const Center(child: CircularProgressIndicator(strokeWidth: 2.4));
                return ListView(
                  shrinkWrap: true,
                  children: [for (final p in snap.data!) _PieceRow(piece: p)],
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _PieceRow extends StatelessWidget {
  const _PieceRow({required this.piece});

  final TaggedPiece piece;

  @override
  Widget build(BuildContext context) {
    return ExpansionTile(
      tilePadding: EdgeInsets.zero,
      leading: SizedBox(width: 48, height: 48, child: GarmentImage(piece.toGarment())),
      title: Text(piece.label, style: DmText.itemName),
      subtitle: Text(
        [piece.color, if (piece.brand != null) 'par ${piece.brand}'].whereType<String>().join(' · '),
        style: DmText.caption,
      ),
      children: [
        if (piece.shop.isEmpty)
          const Padding(
              padding: EdgeInsets.only(bottom: 8),
              child: Text('Rien de proche dans les boutiques tunisiennes.', style: DmText.caption))
        else
          for (final s in piece.shop)
            ListTile(
              dense: true,
              title: Text(s.item, style: DmText.body.copyWith(color: DmColors.text)),
              subtitle: Text(s.shop, style: DmText.caption),
              trailing:
                  s.priceTnd == null ? null : Text('${s.priceTnd!.toStringAsFixed(0)} DT', style: DmText.itemName),
              onTap: s.url == null ? null : () => openLink(context, s.url!),
            ),
      ],
    );
  }
}

/// "Recreate this look": the closest pieces of my own wardrobe (M2 match), and a card to share it.
class RecreateSheet extends ConsumerWidget {
  const RecreateSheet({super.key, this.postId, this.photo, required this.ownerName});

  final String? postId;
  final String? photo;
  final String ownerName;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final repo = ref.read(bo7RepositoryProvider);
    final future = repo.recreate(ref.read(currentUserProvider), postId: postId, photo: photo);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 24),
      child: SingleChildScrollView(
        child: FutureBuilder<RecreateResult>(
          future: future,
          builder: (context, snap) {
            if (snap.hasError) return Text(snap.error.toString(), style: DmText.body);
            if (!snap.hasData) {
              return const Padding(padding: EdgeInsets.all(30), child: Center(child: CircularProgressIndicator()));
            }
            final r = snap.data!;
            return RecreateView(result: r, ownerName: ownerName);
          },
        ),
      ),
    );
  }
}

class RecreateView extends ConsumerWidget {
  const RecreateView({super.key, required this.result, required this.ownerName});

  final RecreateResult result;
  final String ownerName;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final repo = ref.read(bo7RepositoryProvider);
    final r = result;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        DmSectionHeader(
          eyebrow: 'Recréer · M2 ${r.sources['match'] == 'mock' ? '(simulé)' : ''}',
          title: r.origin == 'photo' ? 'Avec tes pièces' : 'Le look de $ownerName, avec tes pièces',
        ),
        const SizedBox(height: 8),
        Text('Ressemblance : ${(r.matchScore * 100).round()} %', style: DmText.itemName),
        if (r.missing.isNotEmpty)
          Text('Il te manque : ${r.missing.join(', ')}', style: DmText.caption.copyWith(color: DmColors.warning)),
        const SizedBox(height: 10),
        SizedBox(
          height: 120,
          child: ListView(
            scrollDirection: Axis.horizontal,
            children: [
              for (final p in r.pieces)
                Container(
                  width: 96,
                  margin: const EdgeInsets.only(right: 8),
                  padding: const EdgeInsets.all(6),
                  decoration: BoxDecoration(
                    color: DmColors.sand,
                    borderRadius: BorderRadius.circular(DmRadius.small),
                  ),
                  child: Column(
                    children: [
                      Expanded(child: GarmentImage(p.toGarment())),
                      Text(p.label, maxLines: 1, overflow: TextOverflow.ellipsis, style: DmText.caption),
                    ],
                  ),
                ),
            ],
          ),
        ),
        if (r.card != null) ...[
          const SizedBox(height: 12),
          ClipRRect(
            borderRadius: BorderRadius.circular(DmRadius.card),
            child: Container(
              color: DmColors.sand,
              constraints: const BoxConstraints(maxHeight: 380),
              child: Image.network(repo.url(r.card!.imageUrl), fit: BoxFit.contain),
            ),
          ),
          const SizedBox(height: 10),
          FilledButton.icon(
            onPressed: () async {
              try {
                await repo.publish(ref.read(currentUserProvider), r.card!.cardId, title: 'Recréé à ma façon');
                refreshFeed(ref);
                if (context.mounted) {
                  Navigator.of(context).maybePop();
                  showSnack(context, 'Publié dans le fil');
                }
              } on Bo7Exception catch (e) {
                if (context.mounted) showSnack(context, e.message);
              }
            },
            icon: const Icon(Icons.send_rounded, size: 18),
            label: const Text('Publier dans le fil'),
          ),
        ],
      ],
    );
  }
}

/// "Profiles like yours" (M5 style vectors, cosine similarity), with a follow button.
class SimilarProfilesStrip extends ConsumerWidget {
  const SimilarProfilesStrip({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return AsyncBody<List<SimilarProfile>>(
      value: ref.watch(similarProfilesProvider),
      compact: true,
      builder: (rows) => SizedBox(
        height: 150,
        child: ListView(
          scrollDirection: Axis.horizontal,
          children: [for (final p in rows) _ProfileCard(profile: p)],
        ),
      ),
    );
  }
}

class _ProfileCard extends ConsumerWidget {
  const _ProfileCard({required this.profile});

  final SimilarProfile profile;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final p = profile;
    return Container(
      width: 150,
      margin: const EdgeInsets.only(right: 10),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: DmColors.surface,
        borderRadius: BorderRadius.circular(DmRadius.card),
        border: Border.all(color: DmColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            UserAvatar(p.userId, radius: 14),
            const SizedBox(width: 6),
            Expanded(child: Text(p.name, style: DmText.itemName, overflow: TextOverflow.ellipsis)),
          ]),
          const SizedBox(height: 4),
          Text('${(p.similarity * 100).round()} % comme toi', style: DmText.caption.copyWith(color: DmColors.bronze)),
          Text(p.tags.join(' · '), maxLines: 2, overflow: TextOverflow.ellipsis, style: DmText.caption),
          const Spacer(),
          SizedBox(
            width: double.infinity,
            child: p.following
                ? OutlinedButton(onPressed: () => _toggle(context, ref, false), child: const Text('Suivi'))
                : FilledButton(onPressed: () => _toggle(context, ref, true), child: const Text('Suivre')),
          ),
        ],
      ),
    );
  }

  Future<void> _toggle(BuildContext context, WidgetRef ref, bool on) async {
    try {
      await ref.read(bo7RepositoryProvider).follow(ref.read(currentUserProvider), profile.userId, on);
      ref.invalidate(similarProfilesProvider);
      refreshFeed(ref);
    } on Bo7Exception catch (e) {
      if (context.mounted) showSnack(context, e.message);
    }
  }
}
