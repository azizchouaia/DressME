// Owner: BO7 · M15 — one challenge: join, log today's outfit, coach message (RAG + LLM), card, leaderboard.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/design/dressme_design.dart';
import '../data/bo7_models.dart';
import '../data/bo7_repository.dart';
import '../logic/bo7_providers.dart';
import 'community_tab.dart';
import 'widgets.dart';

class ChallengeDetailScreen extends ConsumerStatefulWidget {
  const ChallengeDetailScreen({super.key, required this.challengeId});

  final String challengeId;

  @override
  ConsumerState<ChallengeDetailScreen> createState() => _ChallengeDetailScreenState();
}

class _ChallengeDetailScreenState extends ConsumerState<ChallengeDetailScreen> {
  final Set<String> _picked = {};
  final _caption = TextEditingController();
  EntryResult? _result;
  bool _busy = false;

  String get _id => widget.challengeId;

  Future<void> _run(Future<void> Function(Bo7Repository repo, String user) action) async {
    setState(() => _busy = true);
    try {
      await action(ref.read(bo7RepositoryProvider), ref.read(currentUserProvider));
    } on Bo7Exception catch (e) {
      if (mounted) showSnack(context, e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _join() => _run((repo, user) async {
        await repo.join(_id, user);
        refreshChallenge(ref, _id);
      });

  Future<void> _submit() => _run((repo, user) async {
        final r = await repo.submit(_id, user, _picked.toList(), caption: _caption.text.trim());
        setState(() {
          _result = r;
          _picked.clear();
          _caption.clear();
        });
        refreshChallenge(ref, _id);
      });

  @override
  Widget build(BuildContext context) {
    final challenge = ref.watch(challengeProvider(_id));
    return Scaffold(
      appBar: AppBar(title: const Text('Défi')),
      body: AsyncBody<Challenge>(
        value: challenge,
        onRetry: () => ref.invalidate(challengeProvider(_id)),
        builder: (c) => ListView(
          padding: const EdgeInsets.fromLTRB(16, 4, 16, 32),
          children: [
            Bo7Hero(
              eyebrow: c.sponsor != null ? 'Sponsorisé par ${c.sponsor}' : 'Défi · ${c.durationDays} jours',
              title: c.title,
              subtitle: c.description,
            ),
            const SizedBox(height: 12),
            Wrap(spacing: 6, runSpacing: 6, children: [for (final r in c.rules) DmPill(r.description)]),
            if (c.reason != null) ...[
              const SizedBox(height: 8),
              Text(c.reason!, style: DmText.body),
            ],
            const SizedBox(height: 14),
            if (!c.joined)
              FilledButton(
                onPressed: _busy ? null : _join,
                child: Text('Rejoindre pour ${c.durationDays} jours'),
              )
            else
              _ProgressPanel(
                challengeId: _id,
                picked: _picked,
                caption: _caption,
                busy: _busy,
                onToggle: (g) => setState(() => _picked.contains(g.id) ? _picked.remove(g.id) : _picked.add(g.id)),
                onSubmit: _submit,
              ),
            if (_result != null) ...[
              const SizedBox(height: 14),
              _ResultPanel(result: _result!),
            ],
            const SizedBox(height: 14),
            _LeaderboardPanel(challengeId: _id),
            const SizedBox(height: 14),
            _NudgesPanel(challengeId: _id),
            const SizedBox(height: 14),
            Bo7Panel(
              title: 'Publications',
              child: AsyncBody<List<Post>>(
                value: ref.watch(postsProvider(_id)),
                compact: true,
                builder: (posts) => posts.isEmpty
                    ? const Text('Chaque jour validé devient une publication avec sa carte.', style: DmText.body)
                    : Column(children: [for (final p in posts) PostCard(post: p)]),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ProgressPanel extends ConsumerWidget {
  const _ProgressPanel({
    required this.challengeId,
    required this.picked,
    required this.caption,
    required this.busy,
    required this.onToggle,
    required this.onSubmit,
  });

  final String challengeId;
  final Set<String> picked;
  final TextEditingController caption;
  final bool busy;
  final ValueChanged<Garment> onToggle;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return AsyncBody<Progress>(
      value: ref.watch(progressProvider(challengeId)),
      compact: true,
      builder: (p) => Bo7Panel(
        title: p.finished ? 'Défi terminé' : 'Jour ${p.nextDay} : qu\'as-tu porté ?',
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (var d = 1; d <= p.durationDays; d++)
                  _DayDot(day: d, status: p.statusOfDay(d), next: d == p.nextDay),
              ],
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                StatTile('${p.points}', 'points'),
                StatTile('${p.streak}', 'série'),
                StatTile('${p.validDays}/${p.durationDays}', 'jours validés'),
                if (p.completionProbability != null)
                  StatTile('${(p.completionProbability! * 100).round()} %', 'chance de finir (ML)', dark: true),
              ],
            ),
            if (p.badges.isNotEmpty) ...[
              const SizedBox(height: 8),
              Wrap(spacing: 6, children: [for (final b in p.badges) DmPill('🏅 $b')]),
            ],
            if (!p.finished) ...[
              const SizedBox(height: 14),
              AsyncBody<List<Garment>>(
                value: ref.watch(wardrobeProvider),
                compact: true,
                builder: (ward) => GarmentPicker(garments: ward, selected: picked, onToggle: onToggle, height: 320),
              ),
              const SizedBox(height: 10),
              TextField(controller: caption, decoration: const InputDecoration(hintText: 'Légende (facultatif)')),
              const SizedBox(height: 10),
              FilledButton(
                onPressed: busy || picked.isEmpty ? null : onSubmit,
                child: Text(
                    busy ? 'Vérification…' : (picked.isEmpty ? 'Choisis ta tenue' : 'Valider le jour ${p.nextDay}')),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _DayDot extends StatelessWidget {
  const _DayDot({required this.day, required this.status, required this.next});

  final int day;
  final bool? status;
  final bool next;

  @override
  Widget build(BuildContext context) {
    final bg = status == null ? DmColors.surface : (status! ? DmColors.success : const Color(0xFFB0573E));
    return Container(
      width: 38,
      height: 38,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: bg,
        border: Border.all(color: next ? DmColors.bronze : DmColors.border, width: next ? 2.4 : 1.2),
      ),
      child: Text(
        '$day',
        style: TextStyle(
            fontWeight: FontWeight.w700,
            color: status == null ? (next ? DmColors.bronze : DmColors.ink) : Colors.white),
      ),
    );
  }
}

class _ResultPanel extends ConsumerWidget {
  const _ResultPanel({required this.result});

  final EntryResult result;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final r = result;
    final repo = ref.read(bo7RepositoryProvider);
    final ward = ref.watch(wardrobeProvider).valueOrNull ?? const <Garment>[];
    final tomorrow = [for (final id in r.suggestion) ...ward.where((g) => g.id == id)];
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: r.valid ? DmColors.successBg : DmColors.warningBg,
        borderRadius: BorderRadius.circular(DmRadius.panel),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(r.valid ? 'Jour ${r.day} validé' : 'Jour ${r.day} non validé',
                    style: DmText.title.copyWith(fontSize: 21)),
              ),
              TextButton.icon(
                onPressed: () => showPipeline(context, 'Agent challenges', r.pipeline),
                icon: const Icon(Icons.account_tree_outlined, size: 16),
                label: const Text('Voir le pipeline'),
              ),
            ],
          ),
          for (final v in r.violations) Text('• $v', style: DmText.body.copyWith(color: DmColors.warning)),
          if (r.coachMessage != null) ...[
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(color: DmColors.surface, borderRadius: BorderRadius.circular(DmRadius.card)),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(r.coachSource == 'llm' ? 'COACH · LLAMA 3.2 + RAG' : 'COACH', style: DmText.eyebrow),
                  const SizedBox(height: 4),
                  Text(r.coachMessage!, style: DmText.body.copyWith(fontSize: 13, color: DmColors.text)),
                ],
              ),
            ),
          ],
          if (r.post?.cardImageUrl != null) ...[
            const SizedBox(height: 12),
            ClipRRect(
              borderRadius: BorderRadius.circular(DmRadius.card),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxHeight: 420),
                child: Image.network(repo.url(r.post!.cardImageUrl!), fit: BoxFit.contain),
              ),
            ),
            if (r.post?.shareUrl != null)
              TextButton(onPressed: () => openLink(context, r.post!.shareUrl!), child: Text(r.post!.shareUrl!)),
          ],
          if (tomorrow.isNotEmpty) ...[
            const SizedBox(height: 10),
            const Text('DEMAIN, ESSAIE', style: DmText.eyebrow),
            const SizedBox(height: 6),
            SizedBox(
              height: 90,
              child: Row(
                children: [
                  for (final g in tomorrow)
                    Expanded(
                      child: Padding(padding: const EdgeInsets.only(right: 6), child: GarmentImage(g)),
                    ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _LeaderboardPanel extends ConsumerWidget {
  const _LeaderboardPanel({required this.challengeId});

  final String challengeId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final me = ref.watch(currentUserProvider);
    return Bo7Panel(
      title: 'Classement',
      child: AsyncBody<List<LeaderboardRow>>(
        value: ref.watch(leaderboardProvider(challengeId)),
        compact: true,
        builder: (rows) => rows.isEmpty
            ? const Text('Personne n\'a encore rejoint. Rejoins, puis change de profil pour jouer comme une amie.',
                style: DmText.body)
            : Column(
                children: [
                  for (final r in rows)
                    ListTile(
                      dense: true,
                      contentPadding: EdgeInsets.zero,
                      leading: UserAvatar(r.userId, radius: 15),
                      title: Text('${r.rank}. ${r.userId}',
                          style:
                              DmText.itemName.copyWith(fontWeight: r.userId == me ? FontWeight.w800 : FontWeight.w600)),
                      subtitle: Text('${r.validDays} jours · ${r.likes} j\'aime', style: DmText.caption),
                      trailing: Text(r.score.toStringAsFixed(1), style: DmText.price),
                    ),
                ],
              ),
      ),
    );
  }
}

class _NudgesPanel extends ConsumerWidget {
  const _NudgesPanel({required this.challengeId});

  final String challengeId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Bo7Panel(
      title: 'Qui a besoin d\'un rappel',
      subtitle: 'Les participantes à risque d\'abandon (modèle ML), avec une tenue proposée.',
      child: AsyncBody<List<Nudge>>(
        value: ref.watch(nudgesProvider(challengeId)),
        compact: true,
        builder: (rows) => rows.isEmpty
            ? const Text('Tout le monde est à jour.', style: DmText.body)
            : Column(
                children: [
                  for (final n in rows)
                    ListTile(
                      dense: true,
                      contentPadding: EdgeInsets.zero,
                      leading: UserAvatar(n.userId, radius: 15),
                      title: Text(n.message, style: DmText.body.copyWith(color: DmColors.text)),
                      trailing: IconButton(
                        icon: const Icon(Icons.send_rounded, size: 18),
                        onPressed: () => showSnack(context, 'Rappel envoyé à ${n.userId}'),
                      ),
                    ),
                ],
              ),
      ),
    );
  }
}
