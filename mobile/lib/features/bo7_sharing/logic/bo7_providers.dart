// Owner: BO7 — Riverpod state of the BO7 app.
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/bo7_api.dart';
import '../data/bo7_models.dart';
import '../data/bo7_repository.dart';

final bo7RepositoryProvider = Provider<Bo7Repository>((ref) => Bo7Repository(ref.watch(bo7ApiProvider)));

/// Who is using the app. Change it in the profile menu to play as a friend (sarra, amen, yasmine...).
/// TODO(auth): the signed-in user once the API gateway has auth.
final currentUserProvider = StateProvider<String>((ref) => 'usr_042');

/// Selected tab of the BO7 screen: 0 Défis, 1 Communauté, 2 Studio, 3 Garde-robe.
final bo7TabProvider = StateProvider<int>((ref) => 0);

final wardrobeProvider = FutureProvider.autoDispose<List<Garment>>((ref) {
  return ref.watch(bo7RepositoryProvider).wardrobe(ref.watch(currentUserProvider));
});

final challengesProvider = FutureProvider.autoDispose<List<Challenge>>((ref) {
  return ref.watch(bo7RepositoryProvider).challenges(ref.watch(currentUserProvider));
});

final challengeProvider = FutureProvider.autoDispose.family<Challenge, String>((ref, id) {
  return ref.watch(bo7RepositoryProvider).challenge(id, ref.watch(currentUserProvider));
});

final progressProvider = FutureProvider.autoDispose.family<Progress, String>((ref, id) {
  return ref.watch(bo7RepositoryProvider).progress(id, ref.watch(currentUserProvider));
});

final leaderboardProvider = FutureProvider.autoDispose.family<List<LeaderboardRow>, String>((ref, id) {
  return ref.watch(bo7RepositoryProvider).leaderboard(id);
});

final nudgesProvider = FutureProvider.autoDispose.family<List<Nudge>, String>((ref, id) {
  return ref.watch(bo7RepositoryProvider).nudges(id);
});

/// Posts of one challenge, or the whole community feed when the id is null.
final postsProvider = FutureProvider.autoDispose.family<List<Post>, String?>((ref, id) {
  return ref.watch(bo7RepositoryProvider).posts(challengeId: id);
});

final commentsProvider = FutureProvider.autoDispose.family<List<Comment>, String>((ref, postId) {
  return ref.watch(bo7RepositoryProvider).comments(postId);
});

final shopsProvider = FutureProvider<List<Shop>>((ref) async {
  try {
    return await ref.watch(bo7RepositoryProvider).shops();
  } on Bo7Exception {
    return const []; // M7 not available: the app works without shop tags
  }
});

/// Share KPIs of everyone (null) or of one user.
final metricsProvider = FutureProvider.autoDispose.family<ShareMetrics, String?>((ref, userId) {
  return ref.watch(bo7RepositoryProvider).metrics(userId: userId);
});

final ambassadorsProvider = FutureProvider.autoDispose<List<Ambassador>>((ref) {
  return ref.watch(bo7RepositoryProvider).ambassadors();
});

final avatarStatusProvider = FutureProvider.autoDispose<AvatarStatus>((ref) {
  return ref.watch(bo7RepositoryProvider).avatarStatus(ref.watch(currentUserProvider));
});

/// Refreshes everything that depends on a challenge after join / a new day / a like.
void refreshChallenge(WidgetRef ref, String id) {
  ref.invalidate(challengeProvider(id));
  ref.invalidate(progressProvider(id));
  ref.invalidate(leaderboardProvider(id));
  ref.invalidate(nudgesProvider(id));
  ref.invalidate(postsProvider(id));
  ref.invalidate(postsProvider(null));
  ref.invalidate(challengesProvider);
}
