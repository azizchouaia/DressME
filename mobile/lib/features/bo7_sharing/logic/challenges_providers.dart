// Owner: BO7 · M15 — Riverpod state for community challenges
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/bo7_api.dart';
import '../data/challenge_models.dart';
import '../data/challenges_repository.dart';

/// TODO(auth): replace with the signed-in user once the API gateway has auth.
final currentUserIdProvider = Provider<String>((ref) => 'usr_042');

final challengesRepositoryProvider = Provider<ChallengesRepository>(
  (ref) => ApiChallengesRepository(ref.watch(bo7ApiProvider)),
);

final challengesListProvider = FutureProvider.autoDispose<List<Challenge>>((ref) {
  return ref.watch(challengesRepositoryProvider).list(ref.watch(currentUserIdProvider));
});

final challengeProvider = FutureProvider.autoDispose.family<Challenge, String>((ref, id) {
  return ref.watch(challengesRepositoryProvider).get(id, ref.watch(currentUserIdProvider));
});

final progressProvider = FutureProvider.autoDispose.family<ChallengeProgress, String>((ref, id) {
  return ref.watch(challengesRepositoryProvider).progress(id, ref.watch(currentUserIdProvider));
});

final leaderboardProvider = FutureProvider.autoDispose.family<List<LeaderboardRow>, String>((ref, id) {
  return ref.watch(challengesRepositoryProvider).leaderboard(id);
});

/// Posts of one challenge, or of all challenges when the id is null (light feed).
final challengePostsProvider = FutureProvider.autoDispose.family<List<ChallengePost>, String?>((ref, id) {
  return ref.watch(challengesRepositoryProvider).posts(challengeId: id);
});

final wardrobeProvider = FutureProvider<List<WardrobeItem>>((ref) {
  return ref.watch(challengesRepositoryProvider).wardrobe(ref.watch(currentUserIdProvider));
});

/// Join + submit actions for one challenge. Refreshes the related providers after each action.
class ChallengeActions {
  ChallengeActions(this.ref, this.challengeId);
  final Ref ref;
  final String challengeId;

  ChallengesRepository get _repo => ref.read(challengesRepositoryProvider);
  String get _user => ref.read(currentUserIdProvider);

  void _refresh() {
    ref.invalidate(challengeProvider(challengeId));
    ref.invalidate(progressProvider(challengeId));
    ref.invalidate(leaderboardProvider(challengeId));
    ref.invalidate(challengePostsProvider(challengeId));
    ref.invalidate(challengePostsProvider(null));
    ref.invalidate(challengesListProvider);
  }

  Future<void> join() async {
    await _repo.join(challengeId, _user);
    _refresh();
  }

  Future<EntryResult> submit(List<String> itemIds, {String? caption}) async {
    final result = await _repo.submit(challengeId, _user, itemIds, caption: caption);
    _refresh();
    return result;
  }

  Future<void> like(String postId) async {
    await _repo.like(postId, _user);
    ref.invalidate(challengePostsProvider(challengeId));
    ref.invalidate(challengePostsProvider(null));
    ref.invalidate(leaderboardProvider(challengeId));
  }
}

final challengeActionsProvider = Provider.family<ChallengeActions, String>(
  (ref, id) => ChallengeActions(ref, id),
);
