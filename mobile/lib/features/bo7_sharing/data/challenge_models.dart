// Owner: BO7 · M15 Community challenges. Mirrors backend/modules/m15_challenges/contract.py.

double _d(Object? v) => (v as num?)?.toDouble() ?? 0;
int _i(Object? v) => (v as num?)?.toInt() ?? 0;
List<String> _strings(Object? v) => (v as List? ?? const []).map((e) => e.toString()).toList();

class ChallengeRule {
  const ChallengeRule(this.type, this.params);
  final String type;
  final Map<String, dynamic> params;

  factory ChallengeRule.fromJson(Map<String, dynamic> j) =>
      ChallengeRule(j['type'] as String, Map<String, dynamic>.from(j['params'] as Map? ?? const {}));

  /// Human sentence shown in the app.
  String get description {
    switch (type) {
      case 'no_repeat':
        return 'No piece can be worn twice';
      case 'color_theme':
        final colors = _strings(params['colors']).join(', ');
        return params['mode'] == 'any' ? 'At least one piece in $colors' : 'Only $colors pieces';
      case 'category_required':
        return 'Include a ${_strings(params['categories']).join(' / ')} piece';
      case 'capsule_limit':
        return 'Use at most ${params['max_distinct']} different pieces in total';
      case 'local_brand':
        return 'Wear ${params['min'] ?? 1} piece(s) from a Tunisian brand';
      case 'min_items':
        return 'At least ${params['min']} pieces per outfit';
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
  final String? sponsor;
  final double? feasibility; // 0..1: can my wardrobe complete it?
  final double? matchScore;
  final String? reason;

  factory Challenge.fromJson(Map<String, dynamic> j) => Challenge(
        id: j['challenge_id'] as String,
        title: j['title'] as String,
        description: j['description'] as String? ?? '',
        rules: (j['rules'] as List? ?? const [])
            .map((e) => ChallengeRule.fromJson(Map<String, dynamic>.from(e as Map)))
            .toList(),
        durationDays: _i(j['duration_days']),
        tags: _strings(j['tags']),
        participants: _i(j['participants']),
        joined: j['joined'] as bool? ?? false,
        sponsor: j['sponsor'] as String?,
        feasibility: (j['feasibility'] as num?)?.toDouble(),
        matchScore: (j['match_score'] as num?)?.toDouble(),
        reason: j['reason'] as String?,
      );
}

class EntryView {
  const EntryView({required this.day, required this.itemIds, required this.valid, this.violations = const [], this.postId});
  final int day;
  final List<String> itemIds;
  final bool valid;
  final List<String> violations;
  final String? postId;

  factory EntryView.fromJson(Map<String, dynamic> j) => EntryView(
        day: _i(j['day']),
        itemIds: _strings(j['item_ids']),
        valid: j['valid'] as bool? ?? false,
        violations: _strings(j['violations']),
        postId: j['post_id'] as String?,
      );
}

class ChallengeProgress {
  const ChallengeProgress({
    required this.challengeId,
    required this.durationDays,
    required this.daysLogged,
    required this.validDays,
    required this.streak,
    required this.completion,
    required this.points,
    required this.badges,
    required this.entries,
    this.nextDay,
  });

  final String challengeId;
  final int durationDays;
  final int daysLogged;
  final int validDays;
  final int streak;
  final double completion;
  final int points;
  final List<String> badges;
  final List<EntryView> entries;
  final int? nextDay;

  bool get finished => nextDay == null;

  /// null = not logged yet, true = valid, false = rule broken.
  bool? statusOfDay(int day) {
    for (final e in entries) {
      if (e.day == day) return e.valid;
    }
    return null;
  }

  factory ChallengeProgress.fromJson(Map<String, dynamic> j) => ChallengeProgress(
        challengeId: j['challenge_id'] as String,
        durationDays: _i(j['duration_days']),
        daysLogged: _i(j['days_logged']),
        validDays: _i(j['valid_days']),
        streak: _i(j['streak']),
        completion: _d(j['completion']),
        points: _i(j['points']),
        badges: _strings(j['badges']),
        entries: (j['entries'] as List? ?? const [])
            .map((e) => EntryView.fromJson(Map<String, dynamic>.from(e as Map)))
            .toList(),
        nextDay: (j['next_day'] as num?)?.toInt(),
      );
}

class ChallengePost {
  const ChallengePost({
    required this.id,
    required this.userId,
    required this.challengeId,
    required this.day,
    required this.itemIds,
    required this.likes,
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
  final DateTime createdAt;
  final String? caption;
  final String? cardImageUrl;
  final String? shareUrl;

  factory ChallengePost.fromJson(Map<String, dynamic> j) => ChallengePost(
        id: j['post_id'] as String,
        userId: j['user_id'] as String,
        challengeId: j['challenge_id'] as String,
        day: _i(j['day']),
        itemIds: _strings(j['item_ids']),
        likes: _i(j['likes']),
        createdAt: DateTime.tryParse(j['created_at'] as String? ?? '') ?? DateTime.now(),
        caption: j['caption'] as String?,
        cardImageUrl: j['card_image_url'] as String?,
        shareUrl: j['share_url'] as String?,
      );
}

class EntryResult {
  const EntryResult({
    required this.day,
    required this.valid,
    required this.violations,
    required this.suggestion,
    required this.progress,
    this.post,
  });

  final int day;
  final bool valid;
  final List<String> violations;
  final List<String> suggestion;
  final ChallengeProgress progress;
  final ChallengePost? post;

  factory EntryResult.fromJson(Map<String, dynamic> j) => EntryResult(
        day: _i(j['day']),
        valid: j['valid'] as bool? ?? false,
        violations: _strings(j['violations']),
        suggestion: _strings(j['suggestion']),
        progress: ChallengeProgress.fromJson(Map<String, dynamic>.from(j['progress'] as Map)),
        post: j['post'] == null ? null : ChallengePost.fromJson(Map<String, dynamic>.from(j['post'] as Map)),
      );
}

class LeaderboardRow {
  const LeaderboardRow(this.rank, this.userId, this.validDays, this.likes, this.score);
  final int rank;
  final String userId;
  final int validDays;
  final int likes;
  final double score;

  factory LeaderboardRow.fromJson(Map<String, dynamic> j) => LeaderboardRow(
        _i(j['rank']), j['user_id'] as String, _i(j['valid_days']), _i(j['likes']), _d(j['score']));
}

/// Minimal view of a garment for the outfit picker. Comes from M1 (wardrobe) when it is live.
class WardrobeItem {
  const WardrobeItem({required this.id, required this.name, required this.category, required this.colorHex, this.localBrand});
  final String id;
  final String name;
  final String category;
  final String colorHex;
  final String? localBrand;
}
