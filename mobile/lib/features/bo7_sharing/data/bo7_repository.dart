// Owner: BO7 — every call of the BO7 app: M15 (challenges), M10 (cards), M1 (wardrobe through /bo7/demo),
// M7 (Tunisian shops) and the BO9 avatar (/bo7/avatar). Rule 4: the other modules are only called, never copied.
import 'package:dio/dio.dart';

import 'bo7_api.dart';
import 'bo7_models.dart';
import 'bo7_social_models.dart';

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
  List<Map<String, dynamic>> _maps(Object? data) =>
      data is List ? data.map((e) => Map<String, dynamic>.from(e as Map)).toList() : const [];
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

  // ------------------------------------------------------------ BO7 social (/bo7/social)
  // The other teams' modules (M2, M3, M5, M6, M11, M12, M14) are mocked server-side until they are built.

  Future<List<FeedPost>> feed(String userId, {bool following = false}) => _call(() async {
        final r = await _dio
            .get('/bo7/social/feed', queryParameters: {'user_id': userId, 'scope': following ? 'following' : 'all'});
        return _list(r.data).map(FeedPost.fromJson).toList();
      });

  Future<FeedPost> publish(String userId, String cardId, {String? title}) => _call(() async {
        final r = await _dio
            .post('/bo7/social/posts', data: {'user_id': userId, 'card_id': cardId, if (title != null) 'title': title});
        return FeedPost.fromJson(_map(r.data));
      });

  Future<int> likePost(String postId, String userId) => _call(() async {
        final r = await _dio.post('/bo7/social/posts/$postId/like', data: {'user_id': userId});
        return (_map(r.data)['likes'] as num).toInt();
      });

  Future<List<FeedComment>> postComments(String postId) => _call(() async {
        final r = await _dio.get('/bo7/social/posts/$postId/comments');
        return _list(r.data).map(FeedComment.fromJson).toList();
      });

  Future<void> commentPost(String postId, String userId, String text) => _call(() async {
        await _dio.post('/bo7/social/posts/$postId/comments', data: {'user_id': userId, 'text': text});
      });

  /// Pieces of a look (tags), with the Tunisian shops selling something close (M7).
  Future<List<TaggedPiece>> taggedPieces(String ownerId, List<String> itemIds) => _call(() async {
        final r =
            await _dio.get('/bo7/social/pieces', queryParameters: {'user_id': ownerId, 'item_ids': itemIds.join(',')});
        return _maps(_map(r.data)['pieces']).map(TaggedPiece.fromJson).toList();
      });

  Future<SocialCard> createPoll(String userId, Map<String, dynamic> candidate, {String? question}) => _call(() async {
        final r = await _dio.post('/bo7/social/polls', data: {
          'user_id': userId,
          'candidate': candidate,
          if (question != null && question.isNotEmpty) 'question': question
        });
        return SocialCard.fromJson(_map(r.data));
      });

  Future<Poll> vote(String pollId, String voterId, String choice) => _call(() async {
        final r = await _dio.post('/bo7/social/polls/$pollId/vote', data: {'voter_id': voterId, 'choice': choice});
        return Poll.fromJson(_map(r.data));
      });

  Future<List<TaggedPiece>> giveawaySuggestions(String userId) => _call(() async {
        final r = await _dio.get('/bo7/social/giveaway/suggestions', queryParameters: {'user_id': userId});
        return _maps(_map(r.data)['items']).map(TaggedPiece.fromJson).toList();
      });

  Future<SocialCard> createGiveaway(String userId, String itemId,
          {String? size, String condition = 'good', String? city, String? note}) =>
      _call(() async {
        final r = await _dio.post('/bo7/social/giveaways', data: {
          'user_id': userId,
          'item_id': itemId,
          if (size != null && size.isNotEmpty) 'size': size,
          'condition': condition,
          if (city != null && city.isNotEmpty) 'city': city,
          if (note != null && note.isNotEmpty) 'note': note,
        });
        return SocialCard.fromJson(_map(r.data));
      });

  Future<Giveaway> requestGiveaway(String giveawayId, String userId, {String? message}) => _call(() async {
        final r = await _dio.post('/bo7/social/giveaways/$giveawayId/request',
            data: {'user_id': userId, if (message != null) 'message': message});
        return Giveaway.fromJson(_map(r.data));
      });

  Future<Giveaway> give(String giveawayId, String ownerId, String toUser) => _call(() async {
        final r =
            await _dio.post('/bo7/social/giveaways/$giveawayId/give', data: {'user_id': ownerId, 'to_user': toUser});
        return Giveaway.fromJson(_map(r.data));
      });

  Future<SocialCard> board(String userId, List<String> itemIds, {String title = 'My look', bool publish = false}) =>
      _call(() async {
        final r = await _dio.post('/bo7/social/board',
            data: {'user_id': userId, 'item_ids': itemIds, 'title': title, 'publish': publish});
        return SocialCard.fromJson(_map(r.data));
      });

  Future<SocialCard> recap(String userId, {String? month, bool publish = false}) => _call(() async {
        final r = await _dio.post('/bo7/social/recap',
            data: {'user_id': userId, if (month != null) 'month': month, 'publish': publish});
        return SocialCard.fromJson(_map(r.data));
      });

  Future<SocialCard> trip(String userId, String destination, int days, {bool publish = false}) => _call(() async {
        final r = await _dio.post('/bo7/social/trip',
            data: {'user_id': userId, 'destination': destination, 'days': days, 'publish': publish});
        return SocialCard.fromJson(_map(r.data));
      });

  Future<SocialCard> timeline(String userId, {int months = 4, bool publish = false}) => _call(() async {
        final r =
            await _dio.post('/bo7/social/timeline', data: {'user_id': userId, 'months': months, 'publish': publish});
        return SocialCard.fromJson(_map(r.data));
      });

  /// Recreate a look with my own pieces: from a feed post, or from a photo (data URI).
  Future<RecreateResult> recreate(String userId, {String? postId, String? photo}) => _call(() async {
        final r = await _dio.post('/bo7/social/recreate', data: {
          'user_id': userId,
          if (postId != null) 'post_id': postId,
          if (photo != null) 'photo': photo,
        });
        return RecreateResult.fromJson(_map(r.data));
      });

  Future<List<Stylist>> stylists() => _call(() async {
        final r = await _dio.get('/bo7/social/stylists');
        return _maps(_map(r.data)['stylists']).map(Stylist.fromJson).toList();
      });

  Future<List<StylistClient>> stylistClients(String stylistId) => _call(() async {
        final r = await _dio.get('/bo7/social/stylists/$stylistId/clients');
        return _maps(_map(r.data)['clients']).map(StylistClient.fromJson).toList();
      });

  Future<void> stylistShare(String stylistId, String clientId, List<String> itemIds, {String? note}) => _call(() async {
        await _dio.post('/bo7/social/stylist/share', data: {
          'stylist_id': stylistId,
          'client_id': clientId,
          'item_ids': itemIds,
          if (note != null && note.isNotEmpty) 'note': note,
        });
      });

  Future<List<InboxLook>> inbox(String clientId) => _call(() async {
        final r = await _dio.get('/bo7/social/inbox/$clientId');
        return _list(r.data).map(InboxLook.fromJson).toList();
      });

  Future<List<SimilarProfile>> similarProfiles(String userId) => _call(() async {
        final r = await _dio.get('/bo7/social/profiles/similar', queryParameters: {'user_id': userId});
        return _maps(_map(r.data)['profiles']).map(SimilarProfile.fromJson).toList();
      });

  Future<void> follow(String userId, String target, bool on) => _call(() async {
        await _dio.post('/bo7/social/follow', data: {'user_id': userId, 'target': target, 'follow': on});
      });
}
