// Owner: BO7 — the Dart models read the real JSON of the API (samples copied from the running backend).
import 'package:dressme/features/bo7_sharing/data/bo7_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('challenge of M15 (ML recommender + wardrobe fit)', () {
    final c = Challenge.fromJson({
      'challenge_id': 'ch_mono',
      'title': 'Monochrome week',
      'description': 'Five days in black, white and grey only.',
      'rules': [
        {
          'type': 'color_theme',
          'params': {
            'colors': ['black', 'white', 'grey'],
            'mode': 'all'
          },
        },
        {
          'type': 'min_items',
          'params': {'min': 2}
        },
      ],
      'duration_days': 5,
      'tags': ['minimal'],
      'sponsor': null,
      'created_by': 'dressme',
      'participants': 0,
      'joined': false,
      'feasibility': 1.0,
      'match_score': 0.322,
      'ranker': 'ml',
      'reason': 'Your wardrobe has what this challenge needs.',
    });
    expect(c.id, 'ch_mono');
    expect(c.feasibility, 1.0);
    expect(c.rules.first.description, 'Seulement du noir, blanc, gris');
    expect(c.rules.last.description, 'Au moins 2 pièces par tenue');
  });

  test('entry result: coach message, ML chance to finish, post with its card, pipeline', () {
    final r = EntryResult.fromJson({
      'day': 1,
      'valid': true,
      'violations': [],
      'post': {
        'post_id': 'post_1',
        'user_id': 'usr_042',
        'challenge_id': 'ch_mono',
        'day': 1,
        'item_ids': ['a', 'b'],
        'caption': 'Monochrome week · Day 1',
        'card_image_url': '/m10/cards/card_1/image',
        'share_url': 'https://dressme.tn/s/5oASomR',
        'likes': 0,
        'comments': 0,
        'created_at': '2026-10-21T20:13:33.883312Z',
      },
      'suggestion': ['c', 'd'],
      'progress': {
        'challenge_id': 'ch_mono',
        'duration_days': 5,
        'days_logged': 1,
        'valid_days': 1,
        'streak': 1,
        'completion': 0.2,
        'points': 10,
        'badges': ['Starter'],
        'next_day': 2,
        'entries': [
          {
            'day': 1,
            'item_ids': ['a', 'b'],
            'valid': true,
            'violations': [],
            'post_id': 'post_1'
          },
        ],
        'completion_probability': 0.255,
        'risk': 'high_risk',
      },
      'coach_message': 'Day 1 counts, streak 1!',
      'coach_source': 'template',
      'pipeline': [
        {'stage': 'code', 'method': 'ML', 'name': 'Completion prediction', 'detail': 'P(finish) = 0.255'},
      ],
    });
    expect(r.valid, isTrue);
    expect(r.progress.statusOfDay(1), isTrue);
    expect(r.progress.statusOfDay(2), isNull);
    expect(r.progress.completionProbability, 0.255);
    expect(r.post!.cardImageUrl, '/m10/cards/card_1/image');
    expect(r.pipeline.single.method, 'ML');
  });

  test('garment of M1 becomes an M10 card item, with its Tunisian maker', () {
    final g = Garment.fromJson({
      'item_id': 'itm_1',
      'name': 'jebba',
      'category': 'traditional',
      'color_hex': '#EEE8DA',
      'color': 'white',
      'local_tag': 'Sidi Bou Said artisans',
      'photo_url': '/bo7/demo/photos/tn_jebba.png',
      'image': '/srv/demo_wardrobe/tn_jebba.png',
      'source': 'M1',
    });
    expect(g.isTunisian, isTrue);
    expect(g.toCardItem()['brand'], 'Sidi Bou Said artisans');
    expect(g.toCardItem()['image'], '/srv/demo_wardrobe/tn_jebba.png');
  });

  test('share card, metrics and avatar status', () {
    final card = ShareCard.fromJson({
      'card_id': 'card_1',
      'short_code': '4j8dXXM',
      'image_url': '/m10/cards/card_1/image',
      'share_url': 'https://dressme.tn/s/4j8dXXM',
      'caption': 'Mon look du jour',
      'alt_text': 'DressMe outfit card',
      'caption_source': 'llm',
      'channel_links': {'whatsapp': 'https://wa.me/?text=x'},
    });
    expect(card.channelLinks['whatsapp'], startsWith('https://wa.me'));
    final m = ShareMetrics.fromJson({
      'cards': 3,
      'sharers': 1,
      'opens': 1,
      'signups': 1,
      'k_factor': 1.0,
      'channels': [
        {'channel': 'whatsapp', 'opens': 1, 'signups': 1, 'conversion': 1.0},
      ],
      'best_channel': null,
    });
    expect(m.kFactor, 1.0);
    expect(m.channels.single.channel, 'whatsapp');
    final a = AvatarStatus.fromJson({
      'viewer': true,
      'viewer_url': '/bo7/avatar/viewer/',
      'bodies': [],
      'm9': {'image': null, 'mocked': true, 'note': 'M9 is a mock (no image)'},
    });
    expect(a.viewer, isTrue);
    expect(a.m9Image, isNull);
  });
}
