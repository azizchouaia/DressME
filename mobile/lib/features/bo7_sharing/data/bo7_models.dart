// Owner: BO7 — Dart classes for the JSON of M15 (challenges), M10 (share cards), M1 (wardrobe, through
// /bo7/demo/wardrobe), M7 (Tunisian shops) and M9 (avatar status). Field names follow the API exactly.

double _d(Object? v) => (v as num?)?.toDouble() ?? 0;
int _i(Object? v) => (v as num?)?.toInt() ?? 0;
String? _s(Object? v) => v?.toString();
List<String> _strings(Object? v) => (v as List? ?? const []).map((e) => e.toString()).toList();
List<Map<String, dynamic>> _maps(Object? v) =>
    (v as List? ?? const []).map((e) => Map<String, dynamic>.from(e as Map)).toList();
DateTime _date(Object? v) => DateTime.tryParse(v?.toString() ?? '') ?? DateTime.now();

/// French labels of the garment categories of M1.
const categoryLabels = <String, String>{
  'all': 'Tout',
  'top': 'Hauts',
  'bottom': 'Bas',
  'dress': 'Robes',
  'outerwear': 'Vestes',
  'traditional': 'Traditionnel',
  'shoes': 'Chaussures',
  'accessory': 'Accessoires',
};

const categoryOrder = ['top', 'outerwear', 'bottom', 'dress', 'traditional', 'shoes', 'accessory'];

// ---------------------------------------------------------------- wardrobe (M1)

/// One piece of the user's wardrobe, read from M1.
class Garment {
  const Garment({
    required this.id,
    required this.name,
    required this.category,
    required this.colorHex,
    this.color,
    this.localTag,
    this.photoUrl,
    this.image,
    this.source,
  });

  final String id;
  final String name;
  final String category;
  final String colorHex;
  final String? color; // colour name ("black"), used by the M7 search
  final String? localTag; // Tunisian maker / shop (M7)
  final String? photoUrl; // path for the app (/bo7/demo/photos/..., /m01/media/...)
  final String? image; // file of the cutout on the server, given back to /m10/cards
  final String? source;

  bool get isTunisian => localTag != null && localTag!.isNotEmpty;

  factory Garment.fromJson(Map<String, dynamic> j) => Garment(
        id: j['item_id'] as String,
        name: _s(j['name']) ?? _s(j['category']) ?? '',
        category: _s(j['category']) ?? 'top',
        colorHex: _s(j['color_hex']) ?? '#C9C6CC',
        color: _s(j['color']),
        localTag: _s(j['local_tag']),
        photoUrl: _s(j['photo_url']),
        image: _s(j['image']),
        source: _s(j['source']),
      );

  /// The piece as an item of an M10 card.
  Map<String, dynamic> toCardItem() => {
        'item_id': id,
        'category': category,
        'label': name,
        if (image != null) 'image': image,
        'color_hex': colorHex,
        if (isTunisian) 'brand': localTag,
      };
}

// ---------------------------------------------------------------- challenges (M15)

class ChallengeRule {
  const ChallengeRule(this.type, this.params);
  final String type;
  final Map<String, dynamic> params;

  factory ChallengeRule.fromJson(Map<String, dynamic> j) =>
      ChallengeRule(j['type'] as String, Map<String, dynamic>.from(j['params'] as Map? ?? const {}));

  static const _colors = <String, String>{
    'black': 'noir',
    'white': 'blanc',
    'grey': 'gris',
    'beige': 'beige',
    'brown': 'marron',
    'red': 'rouge',
    'pink': 'rose',
    'orange': 'orange',
    'yellow': 'jaune',
    'green': 'vert',
    'blue': 'bleu',
    'navy': 'bleu marine',
    'purple': 'violet',
  };

  /// French sentence shown in the app.
  String get description {
    switch (type) {
      case 'no_repeat':
        return 'Aucune pièce portée deux fois';
      case 'color_theme':
        final colors = _strings(params['colors']).map((c) => _colors[c] ?? c).join(', ');
        return params['mode'] == 'any' ? 'Au moins une pièce en $colors' : 'Seulement du $colors';
      case 'category_required':
        final cats = _strings(params['categories']).map((c) => categoryLabels[c] ?? c).join(' / ');
        return 'Une pièce : $cats';
      case 'capsule_limit':
        return 'Au plus ${params['max_distinct']} pièces différentes en tout';
      case 'local_brand':
        return '${params['min'] ?? 1} pièce(s) d\'un créateur tunisien';
      case 'min_items':
        return 'Au moins ${params['min']} pièces par tenue';
      default:
        return type;
    }
  }
}

class Challenge {
  const Challenge({
    required this.id,
    required this.title,
    required this.description,
    required this.rules,
    required this.durationDays,
    required this.tags,
    required this.participants,
    required this.joined,
    required this.createdBy,
    this.sponsor,
    this.feasibility,
    this.matchScore,
    this.reason,
  });

  final String id;
  final String title;
  final String description;
  final List<ChallengeRule> rules;
  final int durationDays;
  final List<String> tags;
  final int participants;
  final bool joined;
  final String createdBy;
  final String? sponsor;
  final double? feasibility; // 0..1: can my wardrobe complete it?
  final double? matchScore; // ML recommender score
  final String? reason;

  factory Challenge.fromJson(Map<String, dynamic> j) => Challenge(
        id: j['challenge_id'] as String,
        title: _s(j['title']) ?? '',
        description: _s(j['description']) ?? '',
        rules: _maps(j['rules']).map(ChallengeRule.fromJson).toList(),
        durationDays: _i(j['duration_days']),
        tags: _strings(j['tags']),
        participants: _i(j['participants']),
        joined: j['joined'] as bool? ?? false,
        createdBy: _s(j['created_by']) ?? 'dressme',
        sponsor: _s(j['sponsor']),
        feasibility: (j['feasibility'] as num?)?.toDouble(),
        matchScore: (j['match_score'] as num?)?.toDouble(),
        reason: _s(j['reason']),
      );
}

class DayEntry {
  const DayEntry({required this.day, required this.itemIds, required this.valid, required this.violations});
  final int day;
  final List<String> itemIds;
  final bool valid;
  final List<String> violations;

  factory DayEntry.fromJson(Map<String, dynamic> j) => DayEntry(
        day: _i(j['day']),
        itemIds: _strings(j['item_ids']),
        valid: j['valid'] as bool? ?? false,
        violations: _strings(j['violations']),
      );
}

class Progress {
  const Progress({
    required this.durationDays,
    required this.daysLogged,
    required this.validDays,
    required this.streak,
    required this.completion,
    required this.points,
    required this.badges,
    required this.entries,
    this.nextDay,
    this.completionProbability,
    this.risk,
  });

  final int durationDays;
  final int daysLogged;
  final int validDays;
  final int streak;
  final double completion;
  final int points;
  final List<String> badges;
  final List<DayEntry> entries;
  final int? nextDay;
  final double? completionProbability; // ML: chance to finish the challenge
  final String? risk;

  bool get finished => nextDay == null;

  /// null = not logged yet, true = counted, false = a rule was broken.
  bool? statusOfDay(int day) {
    for (final e in entries) {
      if (e.day == day) return e.valid;
    }
    return null;
  }

  factory Progress.fromJson(Map<String, dynamic> j) => Progress(
        durationDays: _i(j['duration_days']),
        daysLogged: _i(j['days_logged']),
        validDays: _i(j['valid_days']),
        streak: _i(j['streak']),
        completion: _d(j['completion']),
        points: _i(j['points']),
        badges: _strings(j['badges']),
        entries: _maps(j['entries']).map(DayEntry.fromJson).toList(),
        nextDay: (j['next_day'] as num?)?.toInt(),
        completionProbability: (j['completion_probability'] as num?)?.toDouble(),
        risk: _s(j['risk']),
      );
}

class Post {
  const Post({
    required this.id,
    required this.userId,
    required this.challengeId,
    required this.day,
    required this.itemIds,
    required this.likes,
    required this.comments,
    required this.createdAt,
    this.caption,
    this.cardImageUrl,
    this.shareUrl,
  });

  final String id;
  final String userId;
  final String challengeId;
  final int day;
  final List<String> itemIds;
  final int likes;
  final int comments;
  final DateTime createdAt;
  final String? caption;
  final String? cardImageUrl;
  final String? shareUrl;

  factory Post.fromJson(Map<String, dynamic> j) => Post(
        id: j['post_id'] as String,
        userId: _s(j['user_id']) ?? '',
        challengeId: _s(j['challenge_id']) ?? '',
        day: _i(j['day']),
        itemIds: _strings(j['item_ids']),
        likes: _i(j['likes']),
        comments: _i(j['comments']),
        createdAt: _date(j['created_at']),
        caption: _s(j['caption']),
        cardImageUrl: _s(j['card_image_url']),
        shareUrl: _s(j['share_url']),
      );
}

class Comment {
  const Comment({required this.id, required this.userId, required this.text, required this.createdAt});
  final String id;
  final String userId;
  final String text;
  final DateTime createdAt;

  factory Comment.fromJson(Map<String, dynamic> j) => Comment(
        id: _s(j['comment_id']) ?? '',
        userId: _s(j['user_id']) ?? '',
        text: _s(j['text']) ?? '',
        createdAt: _date(j['created_at']),
      );
}

/// One step of the agent's pipeline (Input → Code → Output), shown for the "how it works" view.
class PipelineStep {
  const PipelineStep(this.stage, this.method, this.name, this.detail);
  final String stage;
  final String method;
  final String name;
  final String detail;

  factory PipelineStep.fromJson(Map<String, dynamic> j) =>
      PipelineStep(_s(j['stage']) ?? '', _s(j['method']) ?? '', _s(j['name']) ?? '', _s(j['detail']) ?? '');
}

class EntryResult {
  const EntryResult({
    required this.day,
    required this.valid,
    required this.violations,
    required this.suggestion,
    required this.progress,
    required this.pipeline,
    this.post,
    this.coachMessage,
    this.coachSource,
    this.completionCardUrl,
  });

  final int day;
  final bool valid;
  final List<String> violations;
  final List<String> suggestion; // item ids proposed for tomorrow
  final Progress progress;
  final List<PipelineStep> pipeline;
  final Post? post;
  final String? coachMessage; // written by the LLM (or the template)
  final String? coachSource; // "llm" | "template"
  final String? completionCardUrl;

  factory EntryResult.fromJson(Map<String, dynamic> j) => EntryResult(
        day: _i(j['day']),
        valid: j['valid'] as bool? ?? false,
        violations: _strings(j['violations']),
        suggestion: _strings(j['suggestion']),
        progress: Progress.fromJson(Map<String, dynamic>.from(j['progress'] as Map)),
        pipeline: _maps(j['pipeline']).map(PipelineStep.fromJson).toList(),
        post: j['post'] == null ? null : Post.fromJson(Map<String, dynamic>.from(j['post'] as Map)),
        coachMessage: _s(j['coach_message']),
        coachSource: _s(j['coach_source']),
        completionCardUrl: _s(j['completion_card_url']),
      );
}

class LeaderboardRow {
  const LeaderboardRow(this.rank, this.userId, this.validDays, this.likes, this.score);
  final int rank;
  final String userId;
  final int validDays;
  final int likes;
  final double score;

  factory LeaderboardRow.fromJson(Map<String, dynamic> j) =>
      LeaderboardRow(_i(j['rank']), _s(j['user_id']) ?? '', _i(j['valid_days']), _i(j['likes']), _d(j['score']));
}

class Nudge {
  const Nudge({required this.userId, required this.message, this.risk});
  final String userId;
  final String message;
  final String? risk;

  factory Nudge.fromJson(Map<String, dynamic> j) =>
      Nudge(userId: _s(j['user_id']) ?? '', message: _s(j['message']) ?? '', risk: _s(j['risk']));
}

// ---------------------------------------------------------------- share cards (M10)

class ShareCard {
  const ShareCard({
    required this.cardId,
    required this.shortCode,
    required this.imageUrl,
    required this.shareUrl,
    required this.caption,
    required this.altText,
    required this.captionSource,
    required this.channelLinks,
    required this.pipeline,
  });

  final String cardId;
  final String shortCode;
  final String imageUrl;
  final String shareUrl;
  final String caption;
  final String altText;
  final String captionSource;
  final Map<String, String> channelLinks;
  final List<PipelineStep> pipeline;

  factory ShareCard.fromJson(Map<String, dynamic> j) => ShareCard(
        cardId: j['card_id'] as String,
        shortCode: _s(j['short_code']) ?? '',
        imageUrl: _s(j['image_url']) ?? '',
        shareUrl: _s(j['share_url']) ?? '',
        caption: _s(j['caption']) ?? '',
        altText: _s(j['alt_text']) ?? '',
        captionSource: _s(j['caption_source']) ?? 'template',
        channelLinks: (j['channel_links'] as Map? ?? const {}).map((k, v) => MapEntry(k.toString(), v.toString())),
        pipeline: _maps(j['pipeline']).map(PipelineStep.fromJson).toList(),
      );
}

class ChannelStat {
  const ChannelStat(this.channel, this.opens, this.signups);
  final String channel;
  final int opens;
  final int signups;
}

class ShareMetrics {
  const ShareMetrics({
    required this.cards,
    required this.sharers,
    required this.opens,
    required this.signups,
    required this.kFactor,
    required this.channels,
    this.bestChannel,
  });

  final int cards;
  final int sharers;
  final int opens;
  final int signups;
  final double kFactor; // above 1, each user brings more than one new user
  final List<ChannelStat> channels;
  final String? bestChannel;

  factory ShareMetrics.fromJson(Map<String, dynamic> j) => ShareMetrics(
        cards: _i(j['cards']),
        sharers: _i(j['sharers']),
        opens: _i(j['opens']),
        signups: _i(j['signups']),
        kFactor: _d(j['k_factor']),
        channels: _maps(j['channels'])
            .map((c) => ChannelStat(_s(c['channel']) ?? '', _i(c['opens']), _i(c['signups'])))
            .toList(),
        bestChannel: _s(j['best_channel']),
      );
}

class Ambassador {
  const Ambassador(this.rank, this.userId, this.signups, this.points, this.tier);
  final int rank;
  final String userId;
  final int signups;
  final int points;
  final String? tier;

  factory Ambassador.fromJson(Map<String, dynamic> j) =>
      Ambassador(_i(j['rank']), _s(j['user_id']) ?? '', _i(j['signups']), _i(j['points']), _s(j['tier']));
}

// ---------------------------------------------------------------- Tunisian shops (M7)

class Shop {
  const Shop({required this.name, required this.kind, this.city, this.url});
  final String name;
  final String kind; // "Tunisian brand" | "Tunisian shop"
  final String? city;
  final String? url;

  factory Shop.fromJson(Map<String, dynamic> j) =>
      Shop(name: _s(j['shop']) ?? '', kind: _s(j['kind']) ?? '', city: _s(j['city']), url: _s(j['url']));
}

class ShopProduct {
  const ShopProduct({required this.shop, required this.item, this.priceTnd, this.photo, this.url});
  final String shop;
  final String item;
  final double? priceTnd;
  final String? photo;
  final String? url;

  factory ShopProduct.fromJson(Map<String, dynamic> j) => ShopProduct(
        shop: _s(j['shop']) ?? '',
        item: _s(j['item']) ?? '',
        priceTnd: (j['price_tnd'] as num?)?.toDouble(),
        photo: _s(j['photo']),
        url: _s(j['url']),
      );
}

/// "Shop this look in Tunisia": for one of my pieces, the closest products of Tunisian shops.
class LookMatch {
  const LookMatch({required this.itemId, required this.products});
  final String itemId;
  final List<ShopProduct> products;

  factory LookMatch.fromJson(Map<String, dynamic> j) => LookMatch(
        itemId: _s(j['item_id']) ?? '',
        products: _maps(j['products']).map(ShopProduct.fromJson).toList(),
      );
}

// ---------------------------------------------------------------- avatar (BO9 / M9)

class AvatarStatus {
  const AvatarStatus({required this.viewer, required this.viewerUrl, required this.bodies, this.m9Image, this.m9Note});
  final bool viewer; // BO9's viewer is available on the API
  final String viewerUrl;
  final List<String> bodies; // bodies generated by BO9's scripts (SMPL-X); empty = viewer shows no body
  final String? m9Image; // image rendered by M9, when M9 is real
  final String? m9Note;

  factory AvatarStatus.fromJson(Map<String, dynamic> j) {
    final m9 = Map<String, dynamic>.from(j['m9'] as Map? ?? const {});
    return AvatarStatus(
      viewer: j['viewer'] as bool? ?? false,
      viewerUrl: _s(j['viewer_url']) ?? '/bo7/avatar/viewer/',
      bodies: _strings(j['bodies']),
      m9Image: _s(m9['image']),
      m9Note: _s(m9['note']),
    );
  }
}
