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
  static const pageSize = 24;
  static const _maxPage = 100; // M7 accepts up to 100 results per call

  String _query = '';
  String? _city;
  double? _maxPriceTnd;

  @override
  FutureOr<LocalSearchResult?> build() =>
      null; // nothing to load: show the examples at once

  Future<void> search(
      {required String query, String? city, double? maxPriceTnd}) async {
    _query = query;
    _city = city;
    _maxPriceTnd = maxPriceTnd;
    state = const AsyncLoading();
    state = await AsyncValue.guard(
      () => ref.read(localMarketRepositoryProvider).search(
          query: query, city: city, maxPriceTnd: maxPriceTnd, k: pageSize),
    );
  }

  /// Next [pageSize] results of the same search, or every remaining one when [all] is true.
  /// The results already shown stay; on error they stay too and the error is rethrown.
  Future<void> loadMore({bool all = false}) async {
    var current = state.valueOrNull;
    if (current == null || !current.hasMore) return;
    final repo = ref.read(localMarketRepositoryProvider);
    do {
      final remaining = current!.totalMatches - current.results.length;
      final k = all
          ? (remaining < _maxPage ? remaining : _maxPage)
          : (remaining < pageSize ? remaining : pageSize);
      final next = await repo.search(
          query: _query,
          city: _city,
          maxPriceTnd: _maxPriceTnd,
          k: k,
          offset: current.results.length);
      if (next.results.isEmpty) break; // nothing more on the server side
      current = current.append(next);
      state = AsyncData(current);
    } while (all && current.hasMore);
  }

  void clear() => state = const AsyncData(null);
}

final localShopsProvider = FutureProvider<List<LocalShop>>(
    (ref) => ref.read(localMarketRepositoryProvider).shops());
