// Owner: BO7 · M10 — Riverpod state for share cards
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/bo7_api.dart';
import '../data/share_models.dart';
import '../data/share_repository.dart';

final shareRepositoryProvider = Provider<ShareRepository>(
  (ref) => ShareRepository(ref.watch(bo7ApiProvider)),
);

/// Creates one card at a time; the sheet watches it (loading → card → error).
class ShareCardController extends AutoDisposeAsyncNotifier<ShareCard?> {
  @override
  Future<ShareCard?> build() async => null;

  Future<void> create(ShareCardRequest request) async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() => ref.read(shareRepositoryProvider).createCard(request));
  }
}

final shareCardControllerProvider =
    AutoDisposeAsyncNotifierProvider<ShareCardController, ShareCard?>(ShareCardController.new);

final shareMetricsProvider = FutureProvider.autoDispose.family<ShareMetrics, String?>(
  (ref, userId) => ref.watch(shareRepositoryProvider).metrics(userId: userId),
);
