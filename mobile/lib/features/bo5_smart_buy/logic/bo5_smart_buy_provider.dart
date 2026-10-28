// Owner: BO5 (@azizchouaia) — Riverpod state of the Smart Buy screen
import 'package:flutter/foundation.dart' show kDebugMode;
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/bo5_smart_buy_repository.dart';

final smartBuyRepositoryProvider = Provider<SmartBuyRepository>((ref) => SmartBuyRepository());

/// Users, piece types, colours and shop brands for the pickers.
final smartBuyMetaProvider = FutureProvider<SmartBuyMeta>((ref) => ref.read(smartBuyRepositoryProvider).meta());

/// The current verdict (null = nothing asked yet). One session per screen visit: the agent's memory key.
class SmartBuyNotifier extends AsyncNotifier<SmartBuyResult?> {
  late String sessionId;
  String userId = 'usr_demo';
  String language = 'en';

  @override
  Future<SmartBuyResult?> build() async {
    sessionId = 'app-${DateTime.now().millisecondsSinceEpoch}';
    return null;
  }

  SmartBuyRepository get _repo => ref.read(smartBuyRepositoryProvider);

  Future<void> judge({required String probe, double? priceTnd, String? shopBrand, String? fitText, double? aiConfidence}) async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() => _repo.verdict(
          userId: userId,
          probe: probe,
          sessionId: sessionId,
          priceTnd: priceTnd,
          shopBrand: shopBrand,
          fitText: fitText,
          language: language,
          aiConfidence: aiConfidence,
        ));
  }

  Future<void> answer(String questionKey, Object value) async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() => _repo.answer(userId: userId, sessionId: sessionId, questionKey: questionKey, value: value, language: language));
  }

  Future<void> feedback({bool? liked, bool? bought}) async {
    final id = state.valueOrNull?.decisionId;
    if (id != null) await _repo.feedback(userId: userId, decisionId: id, liked: liked, bought: bought);
  }

  void reset() => state = const AsyncData(null);
}

final smartBuyProvider = AsyncNotifierProvider<SmartBuyNotifier, SmartBuyResult?>(SmartBuyNotifier.new);

final shoppingListProvider = FutureProvider.family<List<ShoppingItem>, String>(
    (ref, userId) => ref.read(smartBuyRepositoryProvider).shoppingList(userId));

/// Wishlist of a user (refresh with ref.invalidate after add / remove).
final wishlistProvider = FutureProvider.family<List<WishItem>, String>(
    (ref, userId) => ref.read(smartBuyRepositoryProvider).wishlist(userId));

/// Check-ins waiting for an answer. In debug builds we ask right away (0 days) so the demo works.
const checkinAfterDays = kDebugMode ? 0 : 30;
final checkinsProvider = FutureProvider.family<List<CheckinDue>, String>(
    (ref, userId) => ref.read(smartBuyRepositoryProvider).checkinsDue(userId, days: checkinAfterDays));
