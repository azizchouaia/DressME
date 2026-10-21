// Owner: BO5 (@azizchouaia) — Smart Buy agent (M6) + buy links (M13) + size (M18), through core/api_client.dart
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart' show kIsWeb;

import '../../../core/api_client.dart';

/// API address: `--dart-define=API_URL=http://192.168.1.10:8000` for a real phone; otherwise
/// localhost on the web and 10.0.2.2 (the host machine) on the Android emulator.
String smartBuyApiUrl() {
  const override = String.fromEnvironment('API_URL');
  if (override.isNotEmpty) return override;
  return kIsWeb ? 'http://localhost:8000' : 'http://10.0.2.2:8000';
}

double? _d(Object? v) => (v as num?)?.toDouble();
List<String> _strings(Object? v) => (v as List? ?? const []).map((e) => '$e').toList();

/// What the screen needs to draw its pickers (GET /m06/meta).
class SmartBuyMeta {
  const SmartBuyMeta({required this.users, required this.types, required this.colours, required this.brands});

  final List<({String id, int items})> users;
  final Map<String, List<String>> types; // type -> colours that exist for it
  final Map<String, String> colours; // colour -> hex
  final List<String> brands;

  factory SmartBuyMeta.fromJson(Map<String, dynamic> j) => SmartBuyMeta(
        users: [for (final u in j['users'] as List) (id: u['id'] as String, items: u['items'] as int)],
        types: {
          for (final e in (j['types'] as Map<String, dynamic>).entries)
            e.key: _strings((e.value as Map)['colours'])
        },
        colours: (j['colours'] as Map<String, dynamic>).map((k, v) => MapEntry(k, v as String)),
        brands: _strings(j['brands']),
      );
}

/// Type + colour the AI read on the photo (POST /m06/analyze).
class PhotoGuess {
  const PhotoGuess({required this.subcategory, required this.colour, required this.typeConfidence, required this.colourConfidence});

  final String subcategory;
  final String colour;
  final double typeConfidence;
  final double colourConfidence;

  factory PhotoGuess.fromJson(Map<String, dynamic> j) => PhotoGuess(
        subcategory: j['subcategory'] as String,
        colour: j['colour'] as String,
        typeConfidence: _d((j['confidence'] as Map)['type']) ?? 0,
        colourConfidence: _d((j['confidence'] as Map)['colour']) ?? 0,
      );
}

class BuyLink {
  const BuyLink({required this.shop, required this.item, required this.priceTnd, required this.url, this.city, this.imageUrl, this.productId, this.searchId, this.rank, this.isReal = false});

  final String shop;
  final String item;
  final double priceTnd;
  final String url;
  final String? city;
  final String? imageUrl;
  final String? productId;
  final String? searchId;
  final int? rank;
  final bool isReal;

  factory BuyLink.fromJson(Map<String, dynamic> j) => BuyLink(
        shop: j['shop'] as String,
        item: j['item'] as String,
        priceTnd: _d(j['price_tnd']) ?? 0,
        url: j['url'] as String,
        city: j['city'] as String?,
        imageUrl: j['image_url'] as String?,
        productId: j['product_id'] as String?,
        searchId: j['search_id'] as String?,
        rank: j['rank'] as int?,
        isReal: j['source'] == 'm7',
      );
}

class NextAction {
  const NextAction({required this.action, required this.label, this.tool, this.args = const {}});

  final String action;
  final String label;
  final String? tool;
  final Map<String, dynamic> args;

  factory NextAction.fromJson(Map<String, dynamic> j) => NextAction(
        action: j['action'] as String,
        label: j['label'] as String,
        tool: j['tool'] as String?,
        args: (j['args'] as Map?)?.cast<String, dynamic>() ?? const {},
      );
}

/// The agent's answer (POST /m06/verdict). Only the fields the screen shows.
class SmartBuyResult {
  const SmartBuyResult({
    required this.verdict,
    required this.score,
    required this.piece,
    required this.explanation,
    required this.explanationByAi,
    required this.reasons,
    required this.contributions,
    required this.whatIf,
    required this.similar,
    required this.newOutfits,
    required this.links,
    required this.memoryNotes,
    required this.nextActions,
    required this.sessionId,
    this.question,
    this.questionKey,
    this.size,
    this.sizeNote,
    this.costPerWear,
    this.predictedWears,
    this.decisionId,
    this.fillsGoal,
  });

  final String verdict; // buy | think | skip
  final int score;
  final String piece;
  final String explanation;
  final bool explanationByAi;
  final List<String> reasons;
  final Map<String, double> contributions; // + toward BUY, - toward SKIP
  final List<String> whatIf;
  final List<({String label, double similarity})> similar;
  final int newOutfits;
  final List<BuyLink> links;
  final List<String> memoryNotes;
  final List<NextAction> nextActions;
  final String sessionId;
  final String? question;
  final String? questionKey;
  final String? size;
  final String? sizeNote;
  final double? costPerWear;
  final int? predictedWears;
  final String? decisionId;
  final String? fillsGoal;

  factory SmartBuyResult.fromJson(Map<String, dynamic> j) {
    final size = j['size_advice'] as Map<String, dynamic>?;
    return SmartBuyResult(
      verdict: j['verdict'] as String,
      score: j['score'] as int,
      piece: (j['piece'] as String?) ?? '',
      explanation: (j['explanation'] as String?) ?? '',
      explanationByAi: (j['sources'] as Map?)?['explanation'] == 'llm',
      reasons: _strings(j['reasons']),
      contributions: ((j['contributions'] as Map?) ?? const {}).map((k, v) => MapEntry('$k', (v as num).toDouble())),
      whatIf: _strings(j['what_if']),
      similar: [
        for (final n in (j['similar_items'] as List? ?? const []))
          (label: n['label'] as String, similarity: _d(n['similarity']) ?? 0)
      ],
      newOutfits: (j['new_outfits'] as int?) ?? 0,
      links: [for (final l in (j['buy_links'] as List? ?? const [])) BuyLink.fromJson(l as Map<String, dynamic>)],
      memoryNotes: _strings(j['memory_notes']),
      nextActions: [for (final a in (j['next_actions'] as List? ?? const [])) NextAction.fromJson(a as Map<String, dynamic>)],
      sessionId: (j['session_id'] as String?) ?? 'default',
      question: j['uncertain'] == true ? j['question'] as String? : null,
      questionKey: j['question_key'] as String?,
      size: size?['size'] as String?,
      sizeNote: size?['note'] as String?,
      costPerWear: _d(j['cost_per_wear_tnd']),
      predictedWears: j['predicted_wears'] as int?,
      decisionId: j['decision_id'] as String?,
      fillsGoal: j['fills_goal'] as String?,
    );
  }
}

class ShoppingItem {
  const ShoppingItem({required this.piece, required this.why, required this.newOutfits, this.typicalPrice, this.withinBudget, this.links = const []});

  final String piece;
  final String why;
  final int newOutfits;
  final double? typicalPrice;
  final bool? withinBudget;
  final List<BuyLink> links;

  factory ShoppingItem.fromJson(Map<String, dynamic> j) => ShoppingItem(
        piece: j['piece'] as String,
        why: j['why'] as String,
        newOutfits: (j['new_outfits'] as int?) ?? 0,
        typicalPrice: _d(j['typical_price_tnd']),
        withinBudget: j['within_budget'] as bool?,
        links: [for (final l in (j['links'] as List? ?? const [])) BuyLink.fromJson(l as Map<String, dynamic>)],
      );
}

class SmartBuyRepository {
  SmartBuyRepository([ApiClient? client]) : _dio = (client ?? ApiClient(baseUrl: smartBuyApiUrl())).dio;

  final Dio _dio;

  Future<SmartBuyMeta> meta() async {
    final r = await _dio.get<Map<String, dynamic>>('/m06/meta');
    return SmartBuyMeta.fromJson(r.data!);
  }

  Future<PhotoGuess> analyze(String dataUrl) async {
    final r = await _dio.post<Map<String, dynamic>>('/m06/analyze', data: {'image': dataUrl});
    return PhotoGuess.fromJson(r.data!);
  }

  /// Judge a piece. [probe] = "custom:<type>:<colour>" (after the user confirmed the photo) or a demo id.
  Future<SmartBuyResult> verdict({
    required String userId,
    required String probe,
    required String sessionId,
    double? priceTnd,
    String? shopBrand,
    String? fitText,
    String language = 'en',
    double? aiConfidence,
  }) async {
    final r = await _dio.post<Map<String, dynamic>>('/m06/verdict', data: {
      'user_id': userId,
      'probe_image': probe,
      'session_id': sessionId,
      'language': language,
      if (priceTnd != null) 'price_tnd': priceTnd,
      if (shopBrand != null) 'shop_brand': shopBrand,
      if (fitText != null && fitText.trim().isNotEmpty) 'body': {'fit_text': fitText.trim()},
      if (aiConfidence != null) 'ai_confidence': aiConfidence,
    });
    return SmartBuyResult.fromJson(r.data!);
  }

  /// Answer the agent's question: no new photo, the agent remembers the request (same session).
  Future<SmartBuyResult> answer({required String userId, required String sessionId, required String questionKey, required Object value, String language = 'fr'}) async {
    final r = await _dio.post<Map<String, dynamic>>('/m06/verdict', data: {
      'user_id': userId,
      'session_id': sessionId,
      'language': language,
      'answer': {'question_key': questionKey, 'value': value},
    });
    return SmartBuyResult.fromJson(r.data!);
  }

  Future<void> feedback({required String userId, required String decisionId, bool? bought, bool? liked}) =>
      _dio.post<void>('/m06/feedback', data: {'user_id': userId, 'decision_id': decisionId, 'bought': bought, 'liked': liked});

  /// The user opened a shop link (BO5 KPI, logged in M7's event log).
  Future<void> click(BuyLink l, String userId) async {
    if (l.productId == null) return;
    try {
      await _dio.post<void>('/m13/click', data: {'product_id': l.productId, 'shop': l.shop, 'user_id': userId, 'rank': l.rank, 'search_id': l.searchId});
    } catch (_) {/* a lost click must never block the user */}
  }

  Future<List<ShoppingItem>> shoppingList(String userId) async {
    final r = await _dio.post<Map<String, dynamic>>('/m06/shopping-list', queryParameters: {'user_id': userId});
    return [for (final i in (r.data!['items'] as List)) ShoppingItem.fromJson(i as Map<String, dynamic>)];
  }
}
