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
  String? _gender; // from the request, the user's answer or the agent's memory
  String _session = '';

  /// The request as the user typed it (sent to the stylist with a hand-off).
  String get query => _query;

  @override
  FutureOr<LocalSearchResult?> build() =>
      null; // nothing to load: show the examples at once

  Future<void> search(
      {required String query, String? city, double? maxPriceTnd}) async {
    _query = query;
    _city = city;
    _maxPriceTnd = maxPriceTnd;
    _gender = null;
    // One agent session per search: the user can then just answer its question.
    _session = 'app_${DateTime.now().millisecondsSinceEpoch}';
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      final result = await ref.read(localMarketRepositoryProvider).search(
          query: query,
          city: city,
          maxPriceTnd: maxPriceTnd,
          sessionId: _session,
          k: pageSize);
      _gender = result.parsed?.gender;
      return result;
    });
  }

  /// The user answers the agent's question ("women", "150"): same session, the request is not repeated.
  Future<void> answer(String questionKey, String value) async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      final result = await ref
          .read(localMarketRepositoryProvider)
          .answer(sessionId: _session, questionKey: questionKey, value: value);
      _gender = result.parsed?.gender;
      _maxPriceTnd = result.parsed?.maxPriceTnd ?? _maxPriceTnd;
      return result;
    });
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
      // Pages stay out of the agent session (an answer applies to the first page); the gender
      // answered or remembered is sent again so page 2 matches page 1.
      final next = await repo.search(
          query: _query,
          city: _city,
          maxPriceTnd: _maxPriceTnd,
          gender: _gender,
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
