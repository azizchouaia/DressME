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
    this.corrected,
  });

  final String? subcategory;
  final String? category;
  final String? color;
  final double? maxPriceTnd;
  final double? minPriceTnd;
  final String? city;

  /// Request after typo correction ("colier" -> "collier"), null when nothing was changed.
  final String? corrected;

  factory ParsedQuery.fromJson(Map<String, dynamic> j) => ParsedQuery(
        subcategory: j['subcategory'] as String?,
        category: j['category'] as String?,
        color: j['color'] as String?,
        maxPriceTnd: (j['max_price_tnd'] as num?)?.toDouble(),
        minPriceTnd: (j['min_price_tnd'] as num?)?.toDouble(),
        city: j['city'] as String?,
        corrected: j['corrected'] as String?,
      );
}

class LocalSearchResult {
  const LocalSearchResult(
      {required this.results,
      required this.totalMatches,
      this.parsed,
      this.note});

  final List<LocalProduct> results;
  final int totalMatches;
  final ParsedQuery? parsed;
  final String? note;

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
      return "Serveur DressMe injoignable (${error.requestOptions.baseUrl}). "
          'Lance « uvicorn api.main:app » dans backend/.';
    }
    final detail = error.response?.data is Map
        ? (error.response!.data as Map)['detail']
        : null;
    return 'Erreur ${error.response?.statusCode ?? ''} : ${detail ?? error.message}';
  }
  return error.toString();
}

class LocalMarketRepository {
  LocalMarketRepository([ApiClient? client])
      : _dio = (client ?? ApiClient(baseUrl: defaultApiUrl())).dio;

  final Dio _dio;

  String get baseUrl => _dio.options.baseUrl;

  /// POST /m07/search — free text ("baskets blanches à Tunis 80 TND") plus optional explicit filters.
  Future<LocalSearchResult> search(
      {required String query,
      String? city,
      double? maxPriceTnd,
      int k = 24}) async {
    final res = await _dio.post<Map<String, dynamic>>('/m07/search', data: {
      'query': query,
      'k': k,
      if (city != null) 'city': city,
      if (maxPriceTnd != null) 'max_price_tnd': maxPriceTnd,
    });
    return LocalSearchResult.fromJson(res.data!);
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
