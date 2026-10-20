// Owner: BO7 · M15 — calls the backend through core/api_client.dart
import 'package:dio/dio.dart';

import 'bo7_api.dart';
import 'challenge_models.dart';
import 'demo_wardrobe.dart';

/// Thrown with the backend's message (e.g. "Day 3 is already logged.") so the UI can show it.
class ChallengeException implements Exception {
  ChallengeException(this.message);
  final String message;
  @override
  String toString() => message;
}

abstract class ChallengesRepository {
  Future<List<Challenge>> list(String userId, {bool recommended = true});
  Future<Challenge> get(String challengeId, String userId);
  Future<ChallengeProgress> join(String challengeId, String userId);
  Future<ChallengeProgress> progress(String challengeId, String userId);
  Future<EntryResult> submit(String challengeId, String userId, List<String> itemIds, {String? caption});
  Future<List<LeaderboardRow>> leaderboard(String challengeId);
  Future<List<ChallengePost>> posts({String? challengeId});
  Future<int> like(String postId, String userId);
  Future<List<WardrobeItem>> wardrobe(String userId);
  String absoluteUrl(String path);
}

class ApiChallengesRepository implements ChallengesRepository {
  ApiChallengesRepository(this._api);
  final Bo7Api _api;
  Dio get _dio => _api.dio;

  Future<T> _call<T>(Future<T> Function() f) async {
    try {
      return await f();
    } on DioException catch (e) {
      final data = e.response?.data;
      final detail = data is Map ? data['detail'] : null;
      throw ChallengeException(detail?.toString() ?? 'Network error: is the DressMe server running?');
    }
  }

  List<Map<String, dynamic>> _list(Object? data) =>
      (data as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();

  @override
  Future<List<Challenge>> list(String userId, {bool recommended = true}) => _call(() async {
        final r = await _dio.get('/m15/challenges', queryParameters: {'user_id': userId, 'recommended': recommended});
        return _list(r.data).map(Challenge.fromJson).toList();
      });

  @override
  Future<Challenge> get(String challengeId, String userId) => _call(() async {
        final r = await _dio.get('/m15/challenges/$challengeId', queryParameters: {'user_id': userId});
        return Challenge.fromJson(Map<String, dynamic>.from(r.data as Map));
      });

  @override
  Future<ChallengeProgress> join(String challengeId, String userId) => _call(() async {
        final r = await _dio.post('/m15/challenges/$challengeId/join', data: {'user_id': userId});
        return ChallengeProgress.fromJson(Map<String, dynamic>.from(r.data as Map));
      });

  @override
  Future<ChallengeProgress> progress(String challengeId, String userId) => _call(() async {
        final r = await _dio.get('/m15/challenges/$challengeId/progress', queryParameters: {'user_id': userId});
        return ChallengeProgress.fromJson(Map<String, dynamic>.from(r.data as Map));
      });

  @override
  Future<EntryResult> submit(String challengeId, String userId, List<String> itemIds, {String? caption}) =>
      _call(() async {
        final r = await _dio.post('/m15/challenges/$challengeId/entries', data: {
          'user_id': userId,
          'item_ids': itemIds,
          if (caption != null && caption.isNotEmpty) 'caption': caption,
        });
        return EntryResult.fromJson(Map<String, dynamic>.from(r.data as Map));
      });

  @override
  Future<List<LeaderboardRow>> leaderboard(String challengeId) => _call(() async {
        final r = await _dio.get('/m15/challenges/$challengeId/leaderboard');
        return _list(r.data).map(LeaderboardRow.fromJson).toList();
      });

  @override
  Future<List<ChallengePost>> posts({String? challengeId}) => _call(() async {
        final r = await _dio.get(challengeId == null ? '/m15/challenges/posts/all' : '/m15/challenges/$challengeId/posts');
        return _list(r.data).map(ChallengePost.fromJson).toList();
      });

  @override
  Future<int> like(String postId, String userId) => _call(() async {
        final r = await _dio.post('/m15/challenges/posts/$postId/like', data: {'user_id': userId});
        return ((r.data as Map)['likes'] as num).toInt();
      });

  /// M1 is not live yet: fall back to the demo wardrobe that the backend mock also uses.
  @override
  Future<List<WardrobeItem>> wardrobe(String userId) async {
    try {
      final r = await _dio.get('/wardrobe/items', queryParameters: {'user_id': userId});
      return _list(r.data)
          .map((g) => WardrobeItem(
                id: g['item_id'] as String,
                name: (g['subcategory'] ?? g['category']) as String,
                category: g['category'] as String,
                colorHex: ((g['colors'] as List?)?.isNotEmpty ?? false)
                    ? (g['colors'] as List).first['hex'] as String
                    : '#C9C6CC',
                localBrand: g['local_tag'] as String?,
              ))
          .toList();
    } catch (_) {
      return demoWardrobe;
    }
  }

  @override
  String absoluteUrl(String path) => _api.absolute(path);
}
