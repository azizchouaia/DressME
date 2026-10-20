// Owner: BO7 · M10 Share / export cards. Mirrors backend/modules/m10_share_cards/contract.py.

/// Card kinds understood by the backend.
enum CardKind {
  outfit,
  board,
  tryon,
  recap,
  giveaway,
  challenge,
  styleTimeline,
  trip,
  poll;

  String get wire => this == CardKind.styleTimeline ? 'style_timeline' : name;
}

enum CardFormat { story, square, post }

class CardItem {
  const CardItem({
    required this.itemId,
    required this.category,
    this.label,
    this.image,
    this.colorHex,
    this.brand,
  });

  final String itemId;
  final String category; // top, bottom, dress, outerwear, shoes, accessory, traditional
  final String? label;
  final String? image; // cutout URL from the wardrobe module (M1)
  final String? colorHex;
  final String? brand; // local brand tag (M7)

  Map<String, dynamic> toJson() => {
        'item_id': itemId,
        'category': category,
        if (label != null) 'label': label,
        if (image != null) 'image': image,
        if (colorHex != null) 'color_hex': colorHex,
        if (brand != null) 'brand': brand,
      };
}

class CardStat {
  const CardStat(this.label, this.value);
  final String label;
  final String value;

  Map<String, dynamic> toJson() => {'label': label, 'value': value};
}

/// What any screen sends to create a card. Other BOs (BO4, BO5, BO6, BO9) build one of these
/// and call `showShareCardSheet` — they never draw cards themselves.
class ShareCardRequest {
  const ShareCardRequest({
    required this.userId,
    this.kind = CardKind.outfit,
    this.items = const [],
    this.title,
    this.subtitle,
    this.caption,
    this.stats = const [],
    this.format = CardFormat.story,
    this.sourceId,
    this.watermark = true,
  });

  final String userId;
  final CardKind kind;
  final List<CardItem> items;
  final String? title;
  final String? subtitle;
  final String? caption;
  final List<CardStat> stats;
  final CardFormat format;
  final String? sourceId;
  final bool watermark;

  Map<String, dynamic> toJson() => {
        'user_id': userId,
        'kind': kind.wire,
        'items': items.map((e) => e.toJson()).toList(),
        if (title != null) 'title': title,
        if (subtitle != null) 'subtitle': subtitle,
        if (caption != null) 'caption': caption,
        'stats': stats.map((e) => e.toJson()).toList(),
        'format': format.name,
        if (sourceId != null) 'source_id': sourceId,
        'watermark': watermark,
      };
}

class ShareCard {
  const ShareCard({
    required this.cardId,
    required this.shortCode,
    required this.imageUrl,
    required this.shareUrl,
    required this.width,
    required this.height,
    required this.caption,
    required this.altText,
    required this.backgroundHex,
  });

  final String cardId;
  final String shortCode;
  final String imageUrl;
  final String shareUrl;
  final int width;
  final int height;
  final String caption;
  final String altText;
  final String backgroundHex;

  double get aspectRatio => height == 0 ? 1 : width / height;

  factory ShareCard.fromJson(Map<String, dynamic> j) => ShareCard(
        cardId: j['card_id'] as String,
        shortCode: j['short_code'] as String,
        imageUrl: j['image_url'] as String,
        shareUrl: j['share_url'] as String,
        width: (j['width'] as num).toInt(),
        height: (j['height'] as num).toInt(),
        caption: j['caption'] as String? ?? '',
        altText: j['alt_text'] as String? ?? '',
        backgroundHex: j['background_hex'] as String? ?? '#FFFFFF',
      );
}

class ShareMetrics {
  const ShareMetrics({
    required this.cards,
    required this.opens,
    required this.signups,
    required this.ctr,
    required this.conversion,
    required this.kFactor,
  });

  final int cards;
  final int opens;
  final int signups;
  final double ctr;
  final double conversion;
  final double kFactor;

  factory ShareMetrics.fromJson(Map<String, dynamic> j) => ShareMetrics(
        cards: (j['cards'] as num).toInt(),
        opens: (j['opens'] as num).toInt(),
        signups: (j['signups'] as num).toInt(),
        ctr: (j['ctr'] as num).toDouble(),
        conversion: (j['conversion'] as num).toDouble(),
        kFactor: (j['k_factor'] as num).toDouble(),
      );
}
