// Owner: BO6 — Riverpod state
import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/bo6_local_market_repository.dart';

final localMarketRepositoryProvider =
    Provider<LocalMarketRepository>((ref) => LocalMarketRepository());

/// Result of the last search (null before the first one).
final localSearchProvider =
    AsyncNotifierProvider<LocalSearchNotifier, LocalSearchResult?>(
        LocalSearchNotifier.new);

class LocalSearchNotifier extends AsyncNotifier<LocalSearchResult?> {
  @override
  FutureOr<LocalSearchResult?> build() =>
      null; // nothing to load: show the examples at once

  Future<void> search(
      {required String query, String? city, double? maxPriceTnd}) async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(
      () => ref
          .read(localMarketRepositoryProvider)
          .search(query: query, city: city, maxPriceTnd: maxPriceTnd),
    );
  }

  void clear() => state = const AsyncData(null);
}

final localShopsProvider = FutureProvider<List<LocalShop>>(
    (ref) => ref.read(localMarketRepositoryProvider).shops());
