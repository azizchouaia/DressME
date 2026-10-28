// Owner: BO7 — data of the BO7 social features (/bo7/social): feed, polls, give-aways, tagged pieces,
// recreate a look, stylist looks, similar profiles. The other teams' modules are mocked server-side until built.
import 'bo7_models.dart';

String? _s(Object? v) => v?.toString();
int _i(Object? v) => (v as num?)?.toInt() ?? 0;
double? _d(Object? v) => (v as num?)?.toDouble();
List<String> _strings(Object? v) => v is List ? v.map((e) => e.toString()).toList() : const [];
List<Map<String, dynamic>> _maps(Object? v) =>
    v is List ? v.whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList() : const [];
Map<String, dynamic>? _map(Object? v) => v is Map ? Map<String, dynamic>.from(v) : null;

/// Where an answer came from: the owner's module ("M6"…) or the BO7 mock.
Map<String, String> _sources(Object? v) => (_map(v) ?? const {}).map((k, val) => MapEntry(k, val?.toString() ?? 'n/a'));

/// A piece of a look (tag), from M1, with the Tunisian shops that sell something close (M7).
class TaggedPiece {
  const TaggedPiece({
    required this.itemId,
    required this.category,
    required this.label,
    this.image,
    this.color,
    this.colorHex,
    this.brand,
    this.reason,
    this.shop = const [],
  });

  final String itemId;
  final String category;
  final String label;
  final String? image;
  final String? color;
  final String? colorHex;
  final String? brand;
  final String? reason; // give-away suggestion: why
  final List<ShopProduct> shop;

  factory TaggedPiece.fromJson(Map<String, dynamic> j) => TaggedPiece(
        itemId: _s(j['item_id']) ?? '',
        category: _s(j['category']) ?? '',
        label: _s(j['label']) ?? '',
        image: _s(j['image']),
        color: _s(j['color']),
        colorHex: _s(j['color_hex']),
        brand: _s(j['brand']),
        reason: _s(j['reason']),
        shop: _maps(j['shop']).map(ShopProduct.fromJson).toList(),
      );

  /// As a Garment, to reuse the garment widgets.
  Garment toGarment() => Garment(
        id: itemId,
        name: label,
        category: category,
        colorHex: colorHex ?? '#C9C6CC',
        color: color,
        localTag: brand,
        photoUrl: image,
      );
}

class Poll {
  const Poll({
    required this.id,
    required this.userId,
    required this.question,
    required this.candidate,
    required this.verdict,
    required this.score,
    required this.newOutfits,
    required this.similar,
    required this.yes,
    required this.no,
    this.myVote,
  });

  final String id;
  final String userId;
  final String question;
  final Map<String, dynamic> candidate;
  final String verdict; // buy | think | skip (M6)
  final double score;
  final int newOutfits;
  final int similar;
  final int yes;
  final int no;
  final String? myVote;

  int get total => yes + no;
  double get yesShare => total == 0 ? 0 : yes / total;

  factory Poll.fromJson(Map<String, dynamic> j) {
    final v = _map(j['verdict']) ?? const {};
    final votes = _map(j['votes']) ?? const {};
    return Poll(
      id: _s(j['poll_id']) ?? '',
      userId: _s(j['user_id']) ?? '',
      question: _s(j['question']) ?? '',
      candidate: _map(j['candidate']) ?? const {},
      verdict: _s(v['verdict']) ?? 'think',
      score: _d(v['score']) ?? 0,
      newOutfits: _i(v['new_outfits']),
      similar: (v['similar'] as List?)?.length ?? 0,
      yes: _i(votes['yes']),
      no: _i(votes['no']),
      myVote: _s(j['my_vote']),
    );
  }
}

class GiveawayRequest {
  const GiveawayRequest({required this.userId, required this.userName, this.message});
  final String userId;
  final String userName;
  final String? message;

  factory GiveawayRequest.fromJson(Map<String, dynamic> j) =>
      GiveawayRequest(userId: _s(j['user_id']) ?? '', userName: _s(j['user_name']) ?? '', message: _s(j['message']));
}

class Giveaway {
  const Giveaway({
    required this.id,
    required this.userId,
    required this.itemId,
    required this.status,
    required this.condition,
    required this.requests,
    required this.requested,
    this.size,
    this.city,
    this.givenTo,
  });

  final String id;
  final String userId;
  final String itemId;
  final String status; // open | given
  final String condition;
  final List<GiveawayRequest> requests;
  final bool requested; // did I ask for it?
  final String? size;
  final String? city;
  final String? givenTo;

  bool get open => status == 'open';

  factory Giveaway.fromJson(Map<String, dynamic> j) => Giveaway(
        id: _s(j['giveaway_id']) ?? '',
        userId: _s(j['user_id']) ?? '',
        itemId: _s(j['item_id']) ?? '',
        status: _s(j['status']) ?? 'open',
        condition: _s(j['condition']) ?? '',
        requests: _maps(j['requests']).map(GiveawayRequest.fromJson).toList(),
        requested: j['requested'] == true,
        size: _s(j['size']),
        city: _s(j['city']),
        givenTo: _s(j['given_to']),
      );
}

/// One post of the feed: a card shared by M10 (any kind), or a challenge day of M15.
class FeedPost {
  const FeedPost({
    required this.id,
    required this.source,
    required this.userId,
    required this.userName,
    required this.kind,
    required this.title,
    required this.itemIds,
    required this.likes,
    required this.comments,
    required this.liked,
    required this.createdAt,
    this.caption,
    this.imageUrl,
    this.shareUrl,
    this.poll,
    this.giveaway,
  });

  final String id;
  final String source; // share | challenge
  final String userId;
  final String userName;
  final String kind;
  final String title;
  final List<String> itemIds;
  final int likes;
  final int comments;
  final bool liked;
  final DateTime createdAt;
  final String? caption;
  final String? imageUrl;
  final String? shareUrl;
  final Poll? poll;
  final Giveaway? giveaway;

  factory FeedPost.fromJson(Map<String, dynamic> j) => FeedPost(
        id: _s(j['post_id']) ?? '',
        source: _s(j['source']) ?? 'share',
        userId: _s(j['user_id']) ?? '',
        userName: _s(j['user_name']) ?? _s(j['user_id']) ?? '',
        kind: _s(j['kind']) ?? 'outfit',
        title: _s(j['title']) ?? '',
        itemIds: _strings(j['item_ids']),
        likes: _i(j['likes']),
        comments: _i(j['comments']),
        liked: j['liked'] == true,
        createdAt: DateTime.tryParse(_s(j['created_at']) ?? '') ?? DateTime.now(),
        caption: _s(j['caption']),
        imageUrl: _s(j['image_url']),
        shareUrl: _s(j['share_url']),
        poll: _map(j['poll']) == null ? null : Poll.fromJson(_map(j['poll'])!),
        giveaway: _map(j['giveaway']) == null ? null : Giveaway.fromJson(_map(j['giveaway'])!),
      );
}

class FeedComment {
  const FeedComment({required this.userId, required this.userName, required this.text});
  final String userId;
  final String userName;
  final String text;

  factory FeedComment.fromJson(Map<String, dynamic> j) => FeedComment(
      userId: _s(j['user_id']) ?? '',
      userName: _s(j['user_name']) ?? _s(j['user_id']) ?? '',
      text: _s(j['text']) ?? '');
}

/// A card made by one of the BO7 features (board, recap, trip, timeline, poll, give-away, recreate).
class SocialCard {
  const SocialCard({
    required this.card,
    required this.sources,
    this.post,
    this.extra = const {},
  });

  final ShareCard card;
  final Map<String, String> sources;
  final FeedPost? post;
  final Map<String, dynamic> extra; // the rest of the answer (stats, plan, months, added pieces…)

  factory SocialCard.fromJson(Map<String, dynamic> j) => SocialCard(
        card: ShareCard.fromJson(_map(j['card'])!),
        sources: _sources(j['sources']),
        post: _map(j['post']) == null ? null : FeedPost.fromJson(_map(j['post'])!),
        extra: j,
      );
}

class RecreateResult {
  const RecreateResult({
    required this.origin,
    required this.pieces,
    required this.matchScore,
    required this.missing,
    required this.sources,
    this.inspiredBy,
    this.card,
  });

  final String origin; // look | photo
  final List<TaggedPiece> pieces;
  final double matchScore;
  final List<String> missing; // categories nobody owns
  final Map<String, String> sources;
  final String? inspiredBy;
  final ShareCard? card;

  factory RecreateResult.fromJson(Map<String, dynamic> j) => RecreateResult(
        origin: _s(j['origin']) ?? 'look',
        pieces: _maps(j['pieces']).map(TaggedPiece.fromJson).toList(),
        matchScore: _d(j['match_score']) ?? 0,
        missing: _maps(j['missing']).map((m) => _s(m['category']) ?? '').toList(),
        sources: _sources(j['sources']),
        inspiredBy: _s(j['inspired_by']),
        card: _map(j['card']) == null ? null : ShareCard.fromJson(_map(j['card'])!),
      );
}

class Stylist {
  const Stylist({required this.id, required this.name, this.city, this.speciality});
  final String id;
  final String name;
  final String? city;
  final String? speciality;

  factory Stylist.fromJson(Map<String, dynamic> j) => Stylist(
      id: _s(j['stylist_id']) ?? '', name: _s(j['name']) ?? '', city: _s(j['city']), speciality: _s(j['speciality']));
}

class StylistClient {
  const StylistClient({required this.id, required this.name});
  final String id;
  final String name;

  factory StylistClient.fromJson(Map<String, dynamic> j) =>
      StylistClient(id: _s(j['client_id']) ?? '', name: _s(j['name']) ?? '');
}

/// A look a stylist sent me (M14 → my inbox).
class InboxLook {
  const InboxLook({
    required this.id,
    required this.stylistName,
    required this.itemIds,
    this.imageUrl,
    this.shareUrl,
    this.note,
  });

  final String id;
  final String stylistName;
  final List<String> itemIds;
  final String? imageUrl;
  final String? shareUrl;
  final String? note;

  factory InboxLook.fromJson(Map<String, dynamic> j) => InboxLook(
        id: _s(j['share_id']) ?? '',
        stylistName: _s(j['stylist_name']) ?? '',
        itemIds: _strings(j['item_ids']),
        imageUrl: _s(j['image_url']),
        shareUrl: _s(j['share_url']),
        note: _s(j['note']),
      );
}

class SimilarProfile {
  const SimilarProfile(
      {required this.userId,
      required this.name,
      required this.similarity,
      required this.tags,
      required this.following});
  final String userId;
  final String name;
  final double similarity;
  final List<String> tags;
  final bool following;

  factory SimilarProfile.fromJson(Map<String, dynamic> j) => SimilarProfile(
        userId: _s(j['user_id']) ?? '',
        name: _s(j['name']) ?? '',
        similarity: _d(j['similarity']) ?? 0,
        tags: _strings(j['tags']),
        following: j['following'] == true,
      );
}
