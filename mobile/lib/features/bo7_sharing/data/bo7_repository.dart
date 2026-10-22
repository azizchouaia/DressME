// Owner: BO7 — every call of the BO7 app: M15 (challenges), M10 (cards), M1 (wardrobe through /bo7/demo),
// M7 (Tunisian shops) and the BO9 avatar (/bo7/avatar). Rule 4: the other modules are only called, never copied.
import 'package:dio/dio.dart';

import 'bo7_api.dart';
import 'bo7_models.dart';

/// Error with the server's message (e.g. "Day 3 is already logged."), shown as it is in the app.
class Bo7Exception implements Exception {
  Bo7Exception(this.message);
  final String message;
  @override
  String toString() => message;
}

class Bo7Repository {
  Bo7Repository(this.api);

  final Bo7Api api;
  Dio get _dio => api.dio;

  String url(String path) => api.absolute(path);

  Future<T> _call<T>(Future<T> Function() f) async {
    try {
      return await f();
    } on DioException catch (e) {
      final data = e.response?.data;
      Object? detail = data is Map ? data['detail'] : null;
      if (detail is List) {
        detail = detail.map((d) => d is Map ? d['msg'] : d).join('; ');
      }
      throw Bo7Exception(detail?.toString() ?? 'Serveur injoignable : le serveur DressMe est-il lancé ?');
    }
  }

  Map<String, dynamic> _map(Object? data) => Map<String, dynamic>.from(data as Map);
  List<Map<String, dynamic>> _list(Object? data) =>
      (data as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();

  // ------------------------------------------------------------ M1 wardrobe

  Future<List<Garment>> wardrobe(String userId) => _call(() async {
        final r = await _dio.get('/bo7/demo/wardrobe', queryParameters: {'user_id': userId});
        return _list(r.data).map(Garment.fromJson).toList();
      });

  /// Photo (data URI) → M1 classify → saved in the wardrobe with the name, category and shop typed.
  Future<String> addGarment(
    String userId, {
    required String imageDataUri,
    String? category,
    String? name,
    String? localTag,
  }) =>
      _call(() async {
        final r = await _dio.post('/bo7/demo/wardrobe/items', data: {
          'user_id': userId,
          'image': imageDataUri,
          if (category != null) 'category': category,
          if (name != null && name.isNotEmpty) 'name': name,
          if (localTag != null && localTag.isNotEmpty) 'local_tag': localTag,
        });
        return _map(r.data)['item_id'] as String;
      });

  Future<void> deleteGarment(String userId, String itemId) => _call(() async {
        await _dio.delete('/bo7/demo/wardrobe/items/$itemId', queryParameters: {'user_id': userId});
      });

  // ------------------------------------------------------------ M15 challenges

  Future<List<Challenge>> challenges(String userId) => _call(() async {
        final r = await _dio.get('/m15/challenges', queryParameters: {'user_id': userId});
        return _list(r.data).map(Challenge.fromJson).toList();
      });

  Future<Challenge> challenge(String id, String userId) => _call(() async {
        final r = await _dio.get('/m15/challenges/$id', queryParameters: {'user_id': userId});
        return Challenge.fromJson(_map(r.data));
      });

  Future<Progress> join(String id, String userId) => _call(() async {
        final r = await _dio.post('/m15/challenges/$id/join', data: {'user_id': userId});
        return Progress.fromJson(_map(r.data));
      });

  Future<Progress> progress(String id, String userId) => _call(() async {
        final r = await _dio.get('/m15/challenges/$id/progress', queryParameters: {'user_id': userId});
        return Progress.fromJson(_map(r.data));
      });

  Future<EntryResult> submit(String id, String userId, List<String> itemIds, {String? caption}) => _call(() async {
        final r = await _dio.post('/m15/challenges/$id/entries', data: {
          'user_id': userId,
          'item_ids': itemIds,
          if (caption != null && caption.isNotEmpty) 'caption': caption,
        });
        return EntryResult.fromJson(_map(r.data));
      });

  Future<List<LeaderboardRow>> leaderboard(String id) => _call(() async {
        final r = await _dio.get('/m15/challenges/$id/leaderboard');
        return _list(r.data).map(LeaderboardRow.fromJson).toList();
      });

  Future<List<Nudge>> nudges(String id) => _call(() async {
        final r = await _dio.get('/m15/challenges/$id/nudges', queryParameters: {'all': true});
        return _list(r.data).map(Nudge.fromJson).toList();
      });

  /// Posts of one challenge, or of every challenge (community feed) when [challengeId] is null.
  Future<List<Post>> posts({String? challengeId}) => _call(() async {
        final r =
            await _dio.get(challengeId == null ? '/m15/challenges/posts/all' : '/m15/challenges/$challengeId/posts');
        return _list(r.data).map(Post.fromJson).toList();
      });

  Future<int> like(String postId, String userId) => _call(() async {
        final r = await _dio.post('/m15/challenges/posts/$postId/like', data: {'user_id': userId});
        return (_map(r.data)['likes'] as num).toInt();
      });

  Future<List<Comment>> comments(String postId) => _call(() async {
        final r = await _dio.get('/m15/challenges/posts/$postId/comments');
        return _list(r.data).map(Comment.fromJson).toList();
      });

  Future<Comment> addComment(String postId, String userId, String text) => _call(() async {
        final r = await _dio.post('/m15/challenges/posts/$postId/comments', data: {'user_id': userId, 'text': text});
        return Comment.fromJson(_map(r.data));
      });

  Future<Challenge> createChallenge({
    required String userId,
    required String title,
    required String description,
    required int durationDays,
    required List<Map<String, dynamic>> rules,
  }) =>
      _call(() async {
        final r = await _dio.post('/m15/challenges/create', data: {
          'user_id': userId,
          'title': title,
          'description': description,
          'duration_days': durationDays,
          'rules': rules,
        });
        return Challenge.fromJson(_map(r.data));
      });

  // ------------------------------------------------------------ M10 share cards

  /// [kind]: outfit | board | giveaway | tryon. [avatarImage]: picture of the BO9 avatar (tryon only).
  Future<ShareCard> createCard({
    required String userId,
    required String kind,
    required List<Garment> pieces,
    String? title,
    String? subtitle,
    String format = 'story',
    String language = 'fr',
    bool qr = false,
    String? avatarImage,
  }) =>
      _call(() async {
        final r = await _dio.post('/m10/cards', data: {
          'user_id': userId,
          'kind': kind,
          'items': pieces.map((g) => g.toCardItem()).toList(),
          if (title != null) 'title': title,
          if (subtitle != null) 'subtitle': subtitle,
          'format': format,
          'language': language,
          'qr': qr,
          if (avatarImage != null) 'avatar_image': avatarImage,
        });
        return ShareCard.fromJson(_map(r.data));
      });

  Future<ShareMetrics> metrics({String? userId}) => _call(() async {
        final r = await _dio.get('/m10/metrics', queryParameters: {if (userId != null) 'user_id': userId});
        return ShareMetrics.fromJson(_map(r.data));
      });

  Future<List<Ambassador>> ambassadors() => _call(() async {
        final r = await _dio.get('/m10/ambassadors');
        return _list(r.data).map(Ambassador.fromJson).toList();
      });

  /// Page a friend sees when opening the link (counts the visit for [channel]).
  String friendPage(ShareCard card, String channel) => url('/m10/s/${card.shortCode}/page?ch=$channel');

  // ------------------------------------------------------------ M7 Tunisian shops

  Future<List<Shop>> shops() => _call(() async {
        final r = await _dio.get('/bo7/demo/shops');
        return _list(r.data).map(Shop.fromJson).toList();
      });

  Future<List<LookMatch>> shopTheLook(List<Garment> pieces) => _call(() async {
        final r = await _dio.post('/bo7/demo/shop-the-look', data: {
          'pieces':
              pieces.map((g) => {'item_id': g.id, 'name': g.name, 'color': g.color, 'category': g.category}).toList(),
        });
        return _list(r.data).map(LookMatch.fromJson).toList();
      });

  // ------------------------------------------------------------ BO9 avatar (M9)

  Future<AvatarStatus> avatarStatus(String userId) => _call(() async {
        final r = await _dio.get('/bo7/avatar/status', queryParameters: {'user_id': userId});
        return AvatarStatus.fromJson(_map(r.data));
      });
}
