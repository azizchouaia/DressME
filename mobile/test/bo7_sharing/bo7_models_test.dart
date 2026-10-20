// BO7 · M10 + M15 — JSON parsing must match the backend contracts.
import 'package:dressme/features/bo7_sharing/data/challenge_models.dart';
import 'package:dressme/features/bo7_sharing/data/share_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('ShareCardRequest serialises like the backend contract', () {
    const req = ShareCardRequest(
      userId: 'u1',
      kind: CardKind.styleTimeline,
      items: [CardItem(itemId: 'a', category: 'top', colorHex: '#FFFFFF')],
      stats: [CardStat('months', '6')],
      format: CardFormat.post,
    );
    final j = req.toJson();
    expect(j['kind'], 'style_timeline');
    expect(j['format'], 'post');
    expect((j['items'] as List).first, {'item_id': 'a', 'category': 'top', 'color_hex': '#FFFFFF'});
    expect(j.containsKey('title'), isFalse);
  });

  test('ShareCard.fromJson', () {
    final c = ShareCard.fromJson({
      'card_id': 'card_1', 'short_code': 'Ab3dE9x', 'image_url': '/m10/cards/card_1/image',
      'share_url': 'https://dressme.tn/s/Ab3dE9x', 'width': 1080, 'height': 1920,
      'caption': 'hi', 'alt_text': 'alt', 'background_hex': '#F6F1EA',
    });
    expect(c.aspectRatio, closeTo(0.5625, 1e-6));
  });

  test('Challenge + rule descriptions', () {
    final c = Challenge.fromJson({
      'challenge_id': 'ch_mono', 'title': 'Monochrome week', 'description': 'd', 'duration_days': 5,
      'tags': ['minimal'], 'participants': 3, 'joined': false, 'feasibility': 0.8, 'reason': 'ok',
      'rules': [
        {'type': 'color_theme', 'params': {'colors': ['black', 'white'], 'mode': 'all'}},
        {'type': 'no_repeat', 'params': {}},
      ],
    });
    expect(c.rules.first.description, 'Only black, white pieces');
    expect(c.rules.last.description, 'No piece can be worn twice');
    expect(c.feasibility, 0.8);
  });

  test('EntryResult with progress and post', () {
    final r = EntryResult.fromJson({
      'day': 2, 'valid': false, 'violations': ['straight jeans already worn on day 1'], 'suggestion': ['itm_t3'],
      'post': null,
      'progress': {
        'challenge_id': 'ch_7x7', 'user_id': 'u', 'duration_days': 7, 'days_logged': 2, 'valid_days': 1,
        'streak': 0, 'completion': 0.143, 'points': 10, 'badges': ['Starter'], 'next_day': 3,
        'entries': [
          {'day': 1, 'item_ids': ['a'], 'valid': true, 'violations': [], 'post_id': 'p1'},
          {'day': 2, 'item_ids': ['b'], 'valid': false, 'violations': ['x'], 'post_id': null},
        ],
      },
    });
    expect(r.valid, isFalse);
    expect(r.progress.statusOfDay(1), isTrue);
    expect(r.progress.statusOfDay(2), isFalse);
    expect(r.progress.statusOfDay(3), isNull);
    expect(r.progress.finished, isFalse);
  });
}
