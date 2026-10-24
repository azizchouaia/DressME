// Owner: BO6 — calls the shared module M14 (Stylist / boutique mode) through core/api_client.dart
import 'package:dio/dio.dart';

import '../../../core/api_client.dart';
import '../../bo6_local_market/data/bo6_local_market_repository.dart'
    show defaultApiUrl;

double? _num(Object? v) => (v as num?)?.toDouble();
List<String> _strings(Object? v) => (v as List? ?? const []).cast<String>();

/// A stylist or boutique account (M14 `Pro`).
class Pro {
  const Pro({
    required this.proId,
    required this.type,
    required this.name,
    this.city,
    this.shop,
    this.specialities = const [],
    this.languages = const [],
    this.available = true,
  });

  final String proId;
  final String type; // stylist / boutique
  final String name;
  final String? city;
  final String? shop;
  final List<String> specialities;
  final List<String> languages;
  final bool available;

  bool get isBoutique => type == 'boutique';

  factory Pro.fromJson(Map<String, dynamic> j) => Pro(
        proId: j['pro_id'] as String,
        type: j['type'] as String,
        name: j['name'] as String,
        city: j['city'] as String?,
        shop: j['shop'] as String?,
        specialities: _strings(j['specialities']),
        languages: _strings(j['languages']),
        available: j['available'] as bool? ?? true,
      );
}

/// Tips for a boutique (M14 /dashboard/insights): written by the BO6 LLM (Qwen) or by rules.
class Insights {
  const Insights(
      {required this.tips,
      required this.source,
      required this.facts,
      this.model});

  final List<String> tips;
  final String source; // llm / rules
  final String? model; // qwen2.5:7b
  final List<String> facts;

  factory Insights.fromJson(Map<String, dynamic> j) => Insights(
        tips: _strings(j['insights']),
        source: j['source'] as String,
        model: j['model'] as String?,
        facts: _strings(j['facts']),
      );
}

class Funnel {
  const Funnel(
      {required this.impressions,
      required this.views,
      required this.clicks,
      required this.ctr,
      this.rank});

  final int impressions;
  final int views;
  final int clicks;
  final double ctr;
  final int? rank;

  factory Funnel.fromJson(Map<String, dynamic> j) => Funnel(
        impressions: j['impressions'] as int? ?? 0,
        views: j['views'] as int? ?? 0,
        clicks: j['clicks'] as int? ?? 0,
        ctr: _num(j['ctr']) ?? 0,
        rank: j['rank'] as int?,
      );
}

class DemandTheme {
  const DemandTheme({
    required this.themeId,
    required this.label,
    required this.searches,
    required this.share,
    required this.weakAnswerRate,
    this.medianBudgetTnd,
    this.topCities = const [],
    this.examples = const [],
  });

  final String themeId;
  final String label;
  final int searches;
  final double share;
  final double weakAnswerRate;
  final double? medianBudgetTnd;
  final List<String> topCities;
  final List<String> examples;

  factory DemandTheme.fromJson(Map<String, dynamic> j) => DemandTheme(
        themeId: j['theme_id'] as String,
        label: j['label'] as String,
        searches: j['n_searches'] as int,
        share: _num(j['share']) ?? 0,
        weakAnswerRate: _num(j['weak_answer_rate']) ?? 0,
        medianBudgetTnd: _num(j['median_budget_tnd']),
        topCities: _strings(j['top_cities']),
        examples: _strings(j['examples']),
      );
}

class UnmetDemand {
  const UnmetDemand({
    required this.label,
    required this.searches,
    required this.productsInShop,
    required this.productsInMarket,
    required this.opportunity,
    required this.hint,
  });

  final String label;
  final int searches;
  final int productsInShop;
  final int productsInMarket;
  final double opportunity;
  final String hint;

  factory UnmetDemand.fromJson(Map<String, dynamic> j) => UnmetDemand(
        label: j['label'] as String,
        searches: j['n_searches'] as int,
        productsInShop: j['products_in_shop'] as int,
        productsInMarket: j['products_in_market'] as int,
        opportunity: _num(j['opportunity']) ?? 0,
        hint: j['hint'] as String,
      );
}

class PricePosition {
  const PricePosition({
    required this.label,
    required this.budgets,
    required this.demandP25,
    required this.demandP50,
    required this.demandP75,
    this.shopP50,
    this.servedShare,
  });

  final String label;
  final int budgets;
  final double demandP25;
  final double demandP50;
  final double demandP75;
  final double? shopP50;
  final double? servedShare;

  factory PricePosition.fromJson(Map<String, dynamic> j) => PricePosition(
        label: j['label'] as String,
        budgets: j['n_budgets'] as int,
        demandP25: _num(j['demand_p25'])!,
        demandP50: _num(j['demand_p50'])!,
        demandP75: _num(j['demand_p75'])!,
        shopP50: _num(j['shop_p50']),
        servedShare: _num(j['served_share']),
      );
}

class Trend {
  const Trend({
    required this.label,
    required this.last7Days,
    required this.weeklyMeanBefore,
    required this.z,
    required this.rising,
  });

  final String label;
  final int last7Days;
  final double weeklyMeanBefore;
  final double z;
  final bool rising;

  factory Trend.fromJson(Map<String, dynamic> j) => Trend(
        label: j['label'] as String,
        last7Days: j['last_7_days'] as int,
        weeklyMeanBefore: _num(j['weekly_mean_before']) ?? 0,
        z: _num(j['z']) ?? 0,
        rising: j['rising'] as bool? ?? false,
      );
}

/// M14 `Dashboard`: what users search, at what budget, and what nobody sells.
class Dashboard {
  const Dashboard({
    required this.shop,
    required this.periodDays,
    required this.searches,
    required this.simulatedShare,
    required this.themes,
    required this.unmet,
    required this.prices,
    required this.trends,
    required this.hiddenGroups,
    required this.notUnderstood,
    required this.method,
    this.funnel,
  });

  final String? shop;
  final int periodDays;
  final int searches;
  final double simulatedShare;
  final Funnel? funnel;
  final List<DemandTheme> themes;
  final List<UnmetDemand> unmet;
  final List<PricePosition> prices;
  final List<Trend> trends;
  final int hiddenGroups;
  final int notUnderstood;
  final Map<String, String> method;

  factory Dashboard.fromJson(Map<String, dynamic> j) {
    List<T> list<T>(String key, T Function(Map<String, dynamic>) f) =>
        (j[key] as List? ?? const [])
            .map((e) => f(e as Map<String, dynamic>))
            .toList();
    return Dashboard(
      shop: j['shop'] as String?,
      periodDays: j['period_days'] as int,
      searches: j['n_searches'] as int,
      simulatedShare: _num(j['simulated_share']) ?? 0,
      funnel: j['funnel'] == null
          ? null
          : Funnel.fromJson(j['funnel'] as Map<String, dynamic>),
      themes: list('themes', DemandTheme.fromJson),
      unmet: list('unmet', UnmetDemand.fromJson),
      prices: list('prices', PricePosition.fromJson),
      trends: list('trends', Trend.fromJson),
      hiddenGroups: j['hidden_groups'] as int? ?? 0,
      notUnderstood: j['not_understood'] as int? ?? 0,
      method: (j['method'] as Map? ?? const {}).cast<String, String>(),
    );
  }
}

class Candidate {
  const Candidate(
      {required this.proId,
      required this.name,
      required this.score,
      this.city,
      this.reasons = const []});

  final String proId;
  final String name;
  final String? city;
  final double score;
  final List<String> reasons;

  factory Candidate.fromJson(Map<String, dynamic> j) => Candidate(
        proId: j['pro_id'] as String,
        name: j['name'] as String,
        city: j['city'] as String?,
        score: _num(j['score']) ?? 0,
        reasons: _strings(j['reasons']),
      );
}

/// M14 `Handoff`: a conversation the assistant hands to a human stylist.
class Handoff {
  const Handoff({
    required this.handoffId,
    required this.userId,
    required this.status,
    required this.escalate,
    this.byLlm = false,
    required this.score,
    required this.summary,
    required this.candidates,
    required this.createdAt,
    this.reason,
    this.proId,
    this.occasion,
    this.budgetTnd,
    this.city,
    this.messages = const [],
    this.alreadyOpen = false,
  });

  final String handoffId;
  final String userId;
  final String
      status; // queued / accepted / declined / closed / not_needed / no_stylist
  final bool escalate;

  /// The BO6 LLM added the signal that escalated this chat.
  final bool byLlm;
  final double score;
  final String? reason;
  final String? proId;
  final String? occasion;
  final double? budgetTnd;
  final String? city;
  final List<String> summary;
  final List<Candidate> candidates;
  final DateTime createdAt;

  /// What the client wrote to the assistant before the hand-off.
  final List<String> messages;

  /// The client already had an open request: the server returned that one instead of a new one.
  final bool alreadyOpen;

  bool get isOpen => status == 'queued' || status == 'accepted';

  factory Handoff.fromJson(Map<String, dynamic> j) {
    final esc = j['escalation'] as Map<String, dynamic>;
    return Handoff(
      handoffId: j['handoff_id'] as String,
      userId: j['user_id'] as String,
      status: j['status'] as String,
      escalate: esc['escalate'] as bool,
      byLlm: esc['by_llm'] as bool? ?? false,
      score: _num(esc['score']) ?? 0,
      reason: esc['reason'] as String?,
      proId: j['pro_id'] as String?,
      occasion: j['occasion'] as String?,
      budgetTnd: _num(j['budget_tnd']),
      city: j['city'] as String?,
      summary: _strings(j['summary']),
      candidates: (j['candidates'] as List? ?? const [])
          .map((e) => Candidate.fromJson(e as Map<String, dynamic>))
          .toList(),
      createdAt: DateTime.parse(j['created_at'] as String),
      messages: [
        for (final m in j['messages'] as List? ?? const [])
          if ((m as Map)['role'] == 'user') m['text'] as String
      ],
      alreadyOpen: j['already_open'] as bool? ?? false,
    );
  }
}

/// A piece of the client's wardrobe (M1, through M14).
class WardrobePiece {
  const WardrobePiece({
    required this.itemId,
    required this.category,
    required this.wearCount,
    this.subcategory,
    this.color,
    this.priceTnd,
  });

  final String itemId;
  final String category;
  final String? subcategory;
  final String? color;
  final int wearCount;
  final double? priceTnd;

  factory WardrobePiece.fromJson(Map<String, dynamic> j) => WardrobePiece(
        itemId: j['item_id'] as String,
        category: j['category'] as String,
        subcategory: j['subcategory'] as String?,
        color: j['color'] as String?,
        wearCount: j['wear_count'] as int? ?? 0,
        priceTnd: _num(j['price_tnd']),
      );
}

/// One message of the private stylist <-> client conversation.
class ChatMessage {
  const ChatMessage(
      {required this.senderId,
      required this.role,
      required this.text,
      required this.createdAt,
      this.lookId});

  final String senderId;
  final String role; // stylist / client
  final String text;
  final String? lookId; // the stylist sent a look with this message
  final DateTime createdAt;

  factory ChatMessage.fromJson(Map<String, dynamic> j) => ChatMessage(
        senderId: j['sender_id'] as String,
        role: j['role'] as String,
        text: j['text'] as String,
        lookId: j['look_id'] as String?,
        createdAt: DateTime.parse(j['created_at'] as String),
      );
}

/// Private conversation: only this stylist (with access) and this client can read it.
class Conversation {
  const Conversation({required this.canWrite, required this.messages});

  final bool canWrite; // false once the client revoked the stylist's access
  final List<ChatMessage> messages;

  factory Conversation.fromJson(Map<String, dynamic> j) => Conversation(
        canWrite: j['can_write'] as bool? ?? false,
        messages: (j['messages'] as List? ?? const [])
            .map((e) => ChatMessage.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}

/// A local piece of a look (M7 product).
class LookPiece {
  const LookPiece(
      {required this.productId,
      required this.item,
      required this.shop,
      this.priceTnd,
      this.imagePath,
      this.imageUrl});

  final String productId;
  final String item;
  final String shop;
  final double? priceTnd;
  final String? imagePath;
  final String? imageUrl;

  factory LookPiece.fromJson(Map<String, dynamic> j) => LookPiece(
        productId: j['product_id'] as String,
        item: j['item'] as String,
        shop: j['shop'] as String,
        priceTnd: _num(j['price_tnd']),
        imagePath: j['image_path'] as String?,
        imageUrl: j['image_url'] as String?,
      );
}

/// A look a stylist sent to a client (M14 `Look`).
class Look {
  const Look({
    required this.lookId,
    required this.itemIds,
    required this.products,
    required this.createdAt,
    required this.sources,
    this.score,
    this.totalPriceTnd,
    this.message,
  });

  final String lookId;
  final List<String> itemIds;
  final List<LookPiece> products;
  final double? score;
  final double? totalPriceTnd;
  final String? message;
  final DateTime createdAt;
  final Map<String, String> sources;

  factory Look.fromJson(Map<String, dynamic> j) => Look(
        lookId: j['look_id'] as String,
        itemIds: _strings(j['item_ids']),
        products: (j['products'] as List? ?? const [])
            .map((e) => LookPiece.fromJson(e as Map<String, dynamic>))
            .toList(),
        score: _num(j['score']),
        totalPriceTnd: _num(j['total_price_tnd']),
        message: j['message'] as String?,
        createdAt: DateTime.parse(j['created_at'] as String),
        sources: (j['sources'] as Map? ?? const {}).cast<String, String>(),
      );
}

/// Pro <-> client link (consent).
class ClientLink {
  const ClientLink(
      {required this.linkId,
      required this.proId,
      required this.clientId,
      required this.status});

  final String linkId;
  final String proId;
  final String clientId;
  final String status; // invited / active / declined / revoked

  factory ClientLink.fromJson(Map<String, dynamic> j) => ClientLink(
        linkId: j['link_id'] as String,
        proId: j['pro_id'] as String,
        clientId: j['client_id'] as String,
        status: j['status'] as String,
      );
}

/// M14 `ClientBrief`: what a stylist reads about a client who accepted.
class ClientBrief {
  const ClientBrief({
    required this.clientId,
    required this.summary,
    required this.items,
    required this.perCategory,
    required this.topColours,
    required this.recentSearches,
    required this.sources,
    this.archetype,
  });

  final String clientId;
  final String? archetype;
  final List<String> summary;
  final int items;
  final Map<String, int> perCategory;
  final List<String> topColours;
  final List<String> recentSearches;
  final Map<String, String> sources;

  factory ClientBrief.fromJson(Map<String, dynamic> j) {
    final w = j['wardrobe'] as Map<String, dynamic>;
    return ClientBrief(
      clientId: j['client_id'] as String,
      archetype: j['archetype'] as String?,
      summary: _strings(j['summary']),
      items: w['n_items'] as int? ?? 0,
      perCategory: (w['per_category'] as Map? ?? const {}).cast<String, int>(),
      topColours: _strings(w['top_colours']),
      recentSearches: _strings(j['recent_searches']),
      sources: (j['sources'] as Map? ?? const {}).cast<String, String>(),
    );
  }
}

class BoutiqueRepository {
  BoutiqueRepository([ApiClient? client])
      : _dio = (client ?? ApiClient(baseUrl: defaultApiUrl())).dio;

  final Dio _dio;

  /// GET /m14/pro?type=stylist|boutique
  Future<List<Pro>> pros({String? type}) async {
    final res = await _dio.get<List<dynamic>>('/m14/pro',
        queryParameters: {if (type != null) 'type': type});
    return res.data!
        .map((e) => Pro.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// GET /m14/dashboard?shop= — one shop of the M7 catalogue, or the whole market when [shop] is null.
  /// (A boutique account sees its own shop through /m14/pro/{id}/dashboard; the demo lets you pick any.)
  Future<Dashboard> dashboard({String? shop, int days = 30}) async {
    final res = await _dio.get<Map<String, dynamic>>('/m14/dashboard',
        queryParameters: {'days': days, if (shop != null) 'shop': shop});
    return Dashboard.fromJson(res.data!);
  }

  /// GET /m14/dashboard/insights?shop=&days= — the LLM runs on the CPU: a few seconds to a minute.
  Future<Insights> insights({String? shop, int days = 30}) async {
    final res = await _dio.get<Map<String, dynamic>>('/m14/dashboard/insights',
        queryParameters: {'days': days, if (shop != null) 'shop': shop},
        options: Options(receiveTimeout: const Duration(minutes: 3)));
    return Insights.fromJson(res.data!);
  }

  /// GET /m14/handoff/queue?pro_id= (queued + accepted)
  Future<List<Handoff>> queue(String proId) async {
    final res = await _dio.get<List<dynamic>>('/m14/handoff/queue',
        queryParameters: {'pro_id': proId});
    return res.data!
        .map((e) => Handoff.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// PATCH /m14/handoff/{id}: accepted / declined (goes to the next stylist) / closed
  Future<Handoff> updateHandoff(
      String handoffId, String proId, String status) async {
    final res = await _dio.patch<Map<String, dynamic>>(
        '/m14/handoff/$handoffId',
        data: {'pro_id': proId, 'status': status});
    return Handoff.fromJson(res.data!);
  }

  /// POST /m14/handoff: what the assistant sends when a chat should go to a human.
  Future<Handoff> createHandoff(
      {required String userId,
      required List<String> userMessages,
      bool force = false}) async {
    final res = await _dio.post<Map<String, dynamic>>('/m14/handoff', data: {
      'user_id': userId,
      'session_id': 'app_${DateTime.now().millisecondsSinceEpoch}',
      'language': 'fr',
      'force': force,
      'messages': [
        for (final m in userMessages) {'role': 'user', 'text': m}
      ],
    });
    return Handoff.fromJson(res.data!);
  }

  /// GET /m14/handoff/{id}
  Future<Handoff> handoff(String handoffId) async {
    final res = await _dio.get<Map<String, dynamic>>('/m14/handoff/$handoffId');
    return Handoff.fromJson(res.data!);
  }

  /// GET /m14/clients/{client}/wardrobe?pro_id= (needs the client's consent)
  Future<List<WardrobePiece>> wardrobe(String proId, String clientId) async {
    final res = await _dio.get<Map<String, dynamic>>(
        '/m14/clients/$clientId/wardrobe',
        queryParameters: {'pro_id': proId});
    return (res.data!['items'] as List)
        .map((e) => WardrobePiece.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// POST /m14/looks — wardrobe pieces + local pieces + a message, scored by M2.
  Future<Look> sendLook(
      {required String proId,
      required String clientId,
      required List<String> itemIds,
      required List<String> productIds,
      String? message}) async {
    final res = await _dio.post<Map<String, dynamic>>('/m14/looks', data: {
      'pro_id': proId,
      'client_id': clientId,
      'item_ids': itemIds,
      'product_ids': productIds,
      if (message != null && message.isNotEmpty) 'message': message,
    });
    return Look.fromJson(res.data!);
  }

  /// GET /m14/looks?client_id=&pro_id=
  Future<List<Look>> looks(String proId, String clientId) async {
    final res = await _dio.get<List<dynamic>>('/m14/looks',
        queryParameters: {'pro_id': proId, 'client_id': clientId});
    return res.data!
        .map((e) => Look.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// GET /m14/chat/{pro}/{client}?reader_id= — 403 for anyone but these two people.
  Future<Conversation> conversation(
      String proId, String clientId, String readerId) async {
    final res = await _dio.get<Map<String, dynamic>>(
        '/m14/chat/$proId/$clientId',
        queryParameters: {'reader_id': readerId});
    return Conversation.fromJson(res.data!);
  }

  /// POST /m14/chat/{pro}/{client} — [senderId] is the stylist's pro_id or the client_id.
  Future<void> sendMessage(
      String proId, String clientId, String senderId, String text) async {
    await _dio.post<Map<String, dynamic>>('/m14/chat/$proId/$clientId',
        data: {'sender_id': senderId, 'text': text});
  }

  /// DELETE /m14/chat/{pro}/{client}?requester_id= — only the client (right to be forgotten).
  Future<void> deleteConversation(String proId, String clientId) async {
    await _dio.delete<void>('/m14/chat/$proId/$clientId',
        queryParameters: {'requester_id': clientId});
  }

  /// GET /m14/clients?pro_id=
  Future<List<ClientLink>> links(String proId) async {
    final res = await _dio
        .get<List<dynamic>>('/m14/clients', queryParameters: {'pro_id': proId});
    return res.data!
        .map((e) => ClientLink.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// POST /m14/clients (invitation) — nothing is shared until the client accepts.
  Future<ClientLink> invite(String proId, String clientId) async {
    final res = await _dio.post<Map<String, dynamic>>('/m14/clients',
        data: {'pro_id': proId, 'client_id': clientId});
    return ClientLink.fromJson(res.data!);
  }

  /// POST /m14/clients/{link}/consent — the client's answer (done in the client's app).
  Future<ClientLink> consent(ClientLink link, bool accept) async {
    final res = await _dio.post<Map<String, dynamic>>(
        '/m14/clients/${link.linkId}/consent',
        data: {'client_id': link.clientId, 'accept': accept});
    return ClientLink.fromJson(res.data!);
  }

  /// DELETE /m14/clients/{link}?client_id= — the client takes access back.
  Future<ClientLink> revoke(ClientLink link) async {
    final res = await _dio.delete<Map<String, dynamic>>(
        '/m14/clients/${link.linkId}',
        queryParameters: {'client_id': link.clientId});
    return ClientLink.fromJson(res.data!);
  }

  /// GET /m14/clients/{client}/brief?pro_id= (403 without consent)
  Future<ClientBrief> brief(String proId, String clientId) async {
    final res = await _dio.get<Map<String, dynamic>>(
        '/m14/clients/$clientId/brief',
        queryParameters: {'pro_id': proId});
    return ClientBrief.fromJson(res.data!);
  }

  /// POST /m14/pro — boutique account of a shop of the M7 catalogue (one account per shop).
  Future<Pro> createBoutique(String shop, {String? city}) async {
    final res = await _dio.post<Map<String, dynamic>>('/m14/pro', data: {
      'type': 'boutique',
      'name': shop,
      'shop': shop,
      if (city != null) 'city': city,
    });
    return Pro.fromJson(res.data!);
  }

  /// GET /m14/loyalty?shop= — the shop's valid loyalty code (BO6 Backup 2), or null.
  Future<Map<String, dynamic>?> loyalty(String shop) async {
    final res = await _dio
        .get<List<dynamic>>('/m14/loyalty', queryParameters: {'shop': shop});
    final codes = res.data!.cast<Map<String, dynamic>>();
    return codes.isEmpty ? null : codes.first;
  }

  /// PATCH /m14/pro/{id} {loyalty} — the boutique sets its code (the shop's own agreement).
  Future<void> setLoyalty(String proId, String code, int discountPct,
          {DateTime? until, String? conditions}) =>
      _dio.patch<void>('/m14/pro/$proId', data: {
        'loyalty': {
          'code': code,
          'discount_pct': discountPct,
          if (until != null) 'until': until.toIso8601String().substring(0, 10),
          if (conditions != null && conditions.isNotEmpty)
            'conditions': conditions,
        }
      });

  /// DELETE /m14/pro/{id}/loyalty
  Future<void> removeLoyalty(String proId) =>
      _dio.delete<void>('/m14/pro/$proId/loyalty');

  /// POST /m14/challenges — the boutique sponsors a local brand challenge (BO6 Backup 5, M15).
  Future<Map<String, dynamic>> createChallenge(String proId) async {
    final res = await _dio.post<Map<String, dynamic>>('/m14/challenges',
        data: {'pro_id': proId, 'language': 'en'});
    return res.data!;
  }

  /// POST /m14/challenges/{id}/end — one active challenge per shop: end it to start another.
  Future<void> endChallenge(String challengeId) =>
      _dio.post<void>('/m14/challenges/$challengeId/end');

  /// GET /m14/challenges?pro_id=
  Future<List<Map<String, dynamic>>> challenges(String proId) async {
    final res = await _dio.get<List<dynamic>>('/m14/challenges',
        queryParameters: {'pro_id': proId});
    return res.data!.cast<Map<String, dynamic>>();
  }
}
