// Owner: BO6 — calls the shared module M7 (Local catalogue) through core/api_client.dart
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart' show kIsWeb;

import '../../../core/api_client.dart';

/// API address: `--dart-define=API_URL=http://192.168.1.10:8000` for a real phone; otherwise
/// localhost on the web and 10.0.2.2 (the host machine) on the Android emulator.
String defaultApiUrl() {
  const override = String.fromEnvironment('API_URL');
  if (override.isNotEmpty) return override;
  return kIsWeb ? 'http://localhost:8000' : 'http://10.0.2.2:8000';
}

/// Demo client of the app (no login yet): M7 keeps its memory and M14 its stylist requests under it.
const demoUserId = 'usr_042';

/// One piece sold by a Tunisian shop (M7 `ShopResult`).
class LocalProduct {
  const LocalProduct({
    required this.productId,
    required this.shop,
    required this.item,
    required this.match,
    required this.category,
    required this.subcategory,
    required this.imageUrl,
    required this.productUrl,
    required this.shopUrl,
    required this.originType,
    required this.available,
    this.area,
    this.priceTnd,
    this.color,
    this.size,
    this.imagePath,
    this.reasons = const [],
    this.wardrobeMatches = const [],
    this.loyaltyCode,
    this.loyaltyPct,
  });

  final String productId;
  final String shop;
  final String? area;
  final String item;
  final double? priceTnd;
  final double match;
  final String category;
  final String subcategory;
  final String? color;
  final String? size;
  final String imageUrl;
  final String? imagePath;
  final String productUrl;
  final String shopUrl;
  final String originType;
  final bool available;
  final List<String> reasons;

  /// Pieces of the user's wardrobe it goes with (M1 + M2, simulated until they are merged).
  final List<String> wardrobeMatches;

  /// The shop's loyalty code, set in its boutique account (M14), e.g. MANUELLA10 and -10 %.
  final String? loyaltyCode;
  final int? loyaltyPct;

  bool get isLocalBrand => originType == 'local_brand';

  factory LocalProduct.fromJson(Map<String, dynamic> j) => LocalProduct(
        productId: j['product_id'] as String,
        shop: j['shop'] as String,
        area: j['area'] as String?,
        item: j['item'] as String,
        priceTnd: (j['price_tnd'] as num?)?.toDouble(),
        match: (j['match'] as num).toDouble(),
        category: j['category'] as String,
        subcategory: j['subcategory'] as String,
        color: j['color'] as String?,
        size: j['size'] as String?,
        imageUrl: j['image_url'] as String,
        imagePath: j['image_path'] as String?,
        productUrl: j['product_url'] as String,
        shopUrl: j['shop_url'] as String,
        originType: j['origin_type'] as String,
        available: j['available'] as bool? ?? true,
        reasons: (j['reasons'] as List? ?? const []).cast<String>(),
        loyaltyCode: (j['loyalty'] as Map?)?['code'] as String?,
        loyaltyPct: ((j['loyalty'] as Map?)?['discount_pct'] as num?)?.toInt(),
        wardrobeMatches:
            (j['wardrobe_matches'] as List? ?? const []).cast<String>(),
      );
}

/// How M7 understood the request (filters actually applied).
class ParsedQuery {
  const ParsedQuery({
    this.subcategory,
    this.category,
    this.color,
    this.maxPriceTnd,
    this.minPriceTnd,
    this.city,
    this.gender,
    this.translated,
    this.corrected,
    this.occasion,
    this.season,
    this.usualBudgetTnd,
  });

  final String? subcategory;
  final String? category;
  final String? color;
  final double? maxPriceTnd;
  final double? minPriceTnd;
  final String? city;

  /// "women" / "men" when the request says who the piece is for.
  final String? gender;

  /// Request after darija -> French ("sabbat ahmar" -> "chaussures rouge"), null when not darija.
  final String? translated;

  /// Request after typo correction ("colier" -> "collier"), null when nothing was changed.
  final String? corrected;

  /// Tunisian occasion read in the request (mariage, aïd, ramadan, plage…) and season (summer / winter).
  final String? occasion;
  final String? season;

  /// No budget said: the user's usual budget for this type, learned by the agent's memory (re-ranks only).
  final double? usualBudgetTnd;

  factory ParsedQuery.fromJson(Map<String, dynamic> j) => ParsedQuery(
        subcategory: j['subcategory'] as String?,
        category: j['category'] as String?,
        color: j['color'] as String?,
        maxPriceTnd: (j['max_price_tnd'] as num?)?.toDouble(),
        minPriceTnd: (j['min_price_tnd'] as num?)?.toDouble(),
        city: j['city'] as String?,
        gender: j['gender'] as String?,
        translated: j['translated'] as String?,
        corrected: j['corrected'] as String?,
        occasion: j['occasion'] as String?,
        season: j['season'] as String?,
        usualBudgetTnd: (j['usual_budget_tnd'] as num?)?.toDouble(),
      );
}

/// What the agent proposes next (M7 `NextAction`): ask the user, open the shop, Smart Buy, the stylist…
class NextAction {
  const NextAction(
      {required this.action,
      required this.label,
      this.tool,
      this.args = const {}});

  final String action;
  final String label;

  /// Agent to call next (localshop, smartbuy, stylist); null when the app does it itself.
  final String? tool;
  final Map<String, dynamic> args;

  factory NextAction.fromJson(Map<String, dynamic> j) => NextAction(
        action: j['action'] as String,
        label: j['label'] as String,
        tool: j['tool'] as String?,
        args: (j['args'] as Map?)?.cast<String, dynamic>() ?? const {},
      );
}

class LocalSearchResult {
  const LocalSearchResult(
      {required this.results,
      required this.totalMatches,
      this.parsed,
      this.note,
      this.searchId,
      this.question,
      this.questionKey,
      this.memoryNotes = const [],
      this.nextActions = const []});

  final List<LocalProduct> results;
  final int totalMatches;
  final ParsedQuery? parsed;
  final String? note;

  /// Id of this search in M7's event log, sent back with the clicks (boutique dashboard, M14).
  final String? searchId;

  /// ONE question of the agent ("For women or for men?") and its key, to send back with the answer.
  final String? question;
  final String? questionKey;

  /// What the agent took from its memory ("Pieces for women: your previous answer is remembered.").
  final List<String> memoryNotes;
  final List<NextAction> nextActions;

  /// More results can be loaded ("Show more" / "Show all").
  bool get hasMore => results.length < totalMatches;

  /// This result followed by the next page of the same search (same id, filters, note and question).
  LocalSearchResult append(LocalSearchResult next) => LocalSearchResult(
        results: [...results, ...next.results],
        totalMatches: totalMatches,
        parsed: parsed,
        note: note,
        searchId: searchId,
        question: question,
        questionKey: questionKey,
        memoryNotes: memoryNotes,
        nextActions: nextActions,
      );

  factory LocalSearchResult.fromJson(Map<String, dynamic> j) =>
      LocalSearchResult(
        results: (j['results'] as List)
            .map((e) => LocalProduct.fromJson(e as Map<String, dynamic>))
            .toList(),
        totalMatches: j['total_matches'] as int? ?? 0,
        parsed: j['parsed'] == null
            ? null
            : ParsedQuery.fromJson(j['parsed'] as Map<String, dynamic>),
        note: j['note'] as String?,
        searchId: j['search_id'] as String?,
        question: j['question'] as String?,
        questionKey: j['question_key'] as String?,
        memoryNotes: (j['memory_notes'] as List? ?? const []).cast<String>(),
        nextActions: (j['next_actions'] as List? ?? const [])
            .map((e) => NextAction.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}

class LocalShop {
  const LocalShop(
      {required this.shop,
      required this.shopUrl,
      required this.products,
      this.city,
      this.originType});

  final String shop;
  final String? city;
  final String shopUrl;
  final String? originType;
  final int products;

  factory LocalShop.fromJson(Map<String, dynamic> j) => LocalShop(
        shop: j['shop'] as String,
        city: j['city'] as String?,
        shopUrl: j['shop_url'] as String,
        originType: j['origin_type'] as String?,
        products: j['products'] as int? ?? 0,
      );
}

/// Readable message for the screen when the API cannot be reached or refuses the request.
String describeError(Object error) {
  if (error is DioException) {
    if (error.type == DioExceptionType.connectionError ||
        error.type == DioExceptionType.connectionTimeout) {
      return 'DressMe server unreachable (${error.requestOptions.baseUrl}). '
          'Run "uvicorn api.main:app" in backend/.';
    }
    final detail = error.response?.data is Map
        ? (error.response!.data as Map)['detail']
        : null;
    return 'Error ${error.response?.statusCode ?? ''}: ${detail ?? error.message}';
  }
  return error.toString();
}

class LocalMarketRepository {
  LocalMarketRepository([ApiClient? client])
      : _dio = (client ?? ApiClient(baseUrl: defaultApiUrl())).dio;

  final Dio _dio;

  String get baseUrl => _dio.options.baseUrl;

  /// POST /m07/search — free text ("baskets blanches à Tunis 80 TND") plus optional explicit filters.
  /// [offset]: skip the first results — the next page is the same request with offset += k.
  /// [sessionId]: the agent's memory key, so the user can then just answer its question.
  Future<LocalSearchResult> search(
      {required String query,
      String? city,
      double? maxPriceTnd,
      String? gender,
      String? sessionId,
      int k = 24,
      int offset = 0}) async {
    final res = await _dio.post<Map<String, dynamic>>('/m07/search', data: {
      'query': query,
      'language': 'en', // notes and reasons in English, as the app
      'user_id': demoUserId,
      if (sessionId != null) 'session_id': sessionId,
      'k': k,
      if (offset > 0) 'offset': offset,
      if (city != null) 'city': city,
      if (maxPriceTnd != null) 'max_price_tnd': maxPriceTnd,
      if (gender != null) 'gender': gender,
    });
    return LocalSearchResult.fromJson(res.data!);
  }

  /// The user answers the agent's last question ("women", "150"): M7 reuses the session's request.
  Future<LocalSearchResult> answer(
      {required String sessionId,
      required String questionKey,
      required String value}) async {
    final res = await _dio.post<Map<String, dynamic>>('/m07/search', data: {
      'session_id': sessionId,
      'user_id': demoUserId,
      'language': 'en',
      'answer': {'question_key': questionKey, 'value': value},
    });
    return LocalSearchResult.fromJson(res.data!);
  }

  /// DELETE /m07/memory/{user} — the agent forgets the user's answers and searches.
  Future<void> forget() => _dio.delete<void>('/m07/memory/$demoUserId');

  /// POST /m07/outfits — outfits from the user's wardrobe around one local piece (BO6 idea 3).
  /// POST /m07/try-on — the piece's photo becomes a 3D model by BO9's service (BO6 Selected 6).
  Future<TryOnResult> tryOn(String productId) async {
    final res = await _dio.post<Map<String, dynamic>>('/m07/try-on',
        data: {
          'product_id': productId,
          'user_id': demoUserId,
          'language': 'en'
        },
        options: Options(receiveTimeout: const Duration(minutes: 6)));
    return TryOnResult.fromJson(res.data!);
  }

  /// POST /m07/local-pieces — Tunisian pieces for an outfit of the day (BO6 Selected 4).
  Future<LocalPieces> localPieces(List<String> itemIds) async {
    final res =
        await _dio.post<Map<String, dynamic>>('/m07/local-pieces', data: {
      'user_id': demoUserId,
      'item_ids': itemIds,
      'language': 'en',
    });
    return LocalPieces.fromJson(res.data!);
  }

  Future<LocalOutfits> outfits(String productId) async {
    final res = await _dio.post<Map<String, dynamic>>('/m07/outfits', data: {
      'user_id': demoUserId,
      'product_id': productId,
      'language': 'en',
    });
    return LocalOutfits.fromJson(res.data!);
  }

  /// POST /m07/events — "product_view" (a result was opened) or "shop_click" (the shop's link was taken).
  /// Fire and forget: a lost click must never bother the user.
  Future<void> logEvent(String type, LocalProduct p,
      {String? searchId, int? rank}) async {
    try {
      await _dio.post<void>('/m07/events', data: {
        'type': type,
        'product_id': p.productId,
        'shop': p.shop,
        if (searchId != null) 'search_id': searchId,
        if (rank != null) 'rank': rank,
      });
    } catch (_) {}
  }

  /// GET /m07/shops
  Future<List<LocalShop>> shops() async {
    final res = await _dio.get<List<dynamic>>('/m07/shops');
    return res.data!
        .map((e) => LocalShop.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Local copy served by M7 (/m07/images/...) when available, else the shop's own photo URL.
  String photoUrl(LocalProduct p) =>
      p.imagePath != null ? '$baseUrl/m07/${p.imagePath}' : p.imageUrl;
}

/// One outfit around a local piece: the shop piece + pieces of the user's wardrobe, scored by M2.
class LocalOutfit {
  const LocalOutfit({required this.pieces, required this.score});

  /// (label, from the shop?) in outfit order.
  final List<(String, bool)> pieces;
  final double score;

  factory LocalOutfit.fromJson(Map<String, dynamic> j) => LocalOutfit(
        pieces: [
          for (final p in (j['pieces'] as List).cast<Map<String, dynamic>>())
            (p['label'] as String, p['source'] == 'shop')
        ],
        score: (j['score'] as num).toDouble(),
      );
}

/// POST /m07/outfits answer: outfits, why this local piece, and whether M1 / M2 were real or simulated.
class LocalOutfits {
  const LocalOutfits(
      {required this.piece,
      required this.outfits,
      required this.why,
      required this.simulated});

  final String piece;
  final List<LocalOutfit> outfits;
  final List<String> why;

  /// True while M1 / M2 are not merged: the answer comes from M7's simulation.
  final bool simulated;

  factory LocalOutfits.fromJson(Map<String, dynamic> j) => LocalOutfits(
        piece: j['piece'] as String,
        outfits: (j['outfits'] as List)
            .map((e) => LocalOutfit.fromJson(e as Map<String, dynamic>))
            .toList(),
        why: (j['why'] as List? ?? const []).cast<String>(),
        simulated:
            ((j['sources'] as Map?) ?? const {}).values.any((v) => v == 'mock'),
      );
}

/// One Tunisian piece for an outfit: it completes it (shoes, bag...) or replaces one of its pieces.
class LocalSuggestion {
  const LocalSuggestion(
      {required this.replaces,
      required this.product,
      required this.score,
      required this.reasons});

  final String? replaces;
  final LocalProduct product;
  final double score;
  final List<String> reasons;

  factory LocalSuggestion.fromJson(Map<String, dynamic> j) => LocalSuggestion(
        replaces: j['replaces'] as String?,
        product: LocalProduct.fromJson(j['product'] as Map<String, dynamic>),
        score: (j['score'] as num).toDouble(),
        reasons: (j['reasons'] as List? ?? const []).cast<String>(),
      );
}

/// POST /m07/local-pieces answer.
class LocalPieces {
  const LocalPieces(
      {required this.outfit,
      required this.suggestions,
      required this.simulated});

  final List<String> outfit;
  final List<LocalSuggestion> suggestions;
  final bool simulated;

  factory LocalPieces.fromJson(Map<String, dynamic> j) => LocalPieces(
        outfit: (j['outfit'] as List).cast<String>(),
        suggestions: (j['suggestions'] as List)
            .map((e) => LocalSuggestion.fromJson(e as Map<String, dynamic>))
            .toList(),
        simulated:
            ((j['sources'] as Map?) ?? const {}).values.any((v) => v == 'mock'),
      );
}

/// POST /m07/try-on answer: a 3D model of the piece for the avatar, or the simulation's note.
class TryOnResult {
  const TryOnResult(
      {required this.piece,
      required this.note,
      required this.modelUrl,
      required this.simulated});

  final String piece;
  final String note;

  /// Path of the GLB served by M7 (/m07/try-on/<id>.glb); null while BO9's service is simulated.
  final String? modelUrl;
  final bool simulated;

  factory TryOnResult.fromJson(Map<String, dynamic> j) => TryOnResult(
        piece: j['piece'] as String,
        note: j['note'] as String,
        modelUrl: j['model_url'] as String?,
        simulated: ((j['sources'] as Map?) ?? const {})['m9'] != 'real',
      );
}
