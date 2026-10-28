// Owner: BO7 — the social models read the real JSON of /bo7/social (samples copied from the running backend).
import 'package:dressme/features/bo7_sharing/data/bo7_social_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('feed post with a give-away', () {
    final p = FeedPost.fromJson({
      'post_id': 'fp_1f3b8a891a',
      'source': 'share',
      'user_id': 'usr_042',
      'user_name': 'Omar',
      'kind': 'giveaway',
      'title': 'Give-away · grey t-shirt',
      'image_url': '/m10/cards/card_00b4e5771b70/image',
      'share_url': 'https://dressme.tn/s/qgmRyZB',
      'card_id': 'card_00b4e5771b70',
      'item_ids': ['itm_488429ffc4b9'],
      'likes': 0,
      'comments': 0,
      'liked': false,
      'created_at': '2026-10-26T17:16:57+00:00',
      'poll': null,
      'giveaway': {
        'giveaway_id': 'give_23d27687d7',
        'user_id': 'usr_042',
        'item_id': 'itm_488429ffc4b9',
        'post_id': 'fp_1f3b8a891a',
        'size': 'M',
        'condition': 'good',
        'city': null,
        'note': null,
        'status': 'open',
        'given_to': null,
        'requests': [
          {'user_id': 'amen', 'user_name': 'Amen', 'message': 'Me please', 'created_at': '2026-10-26T17:20:00+00:00'}
        ],
        'requested': false,
      },
    });
    expect(p.kind, 'giveaway');
    expect(p.poll, isNull);
    expect(p.giveaway!.open, isTrue);
    expect(p.giveaway!.requests.single.userName, 'Amen');
    expect(p.createdAt.year, 2026);
  });

  test('poll with the M6 verdict and votes', () {
    final poll = Poll.fromJson({
      'poll_id': 'poll_2c970e2024',
      'user_id': 'usr_042',
      'question': 'Should I buy this red jacket?',
      'candidate': {'label': 'red jacket', 'category': 'outerwear', 'color_hex': '#9A1B1B'},
      'verdict': {
        'verdict': 'skip',
        'score': 0.0,
        'similar': ['itm_a98680889d02'],
        'new_outfits': 0,
        'source': 'mock'
      },
      'votes': {'yes': 3, 'no': 1},
      'my_vote': 'yes',
    });
    expect(poll.verdict, 'skip');
    expect(poll.similar, 1);
    expect(poll.total, 4);
    expect(poll.yesShare, 0.75);
    expect(poll.myVote, 'yes');
  });

  test('recreate a look: my closest pieces and where each answer came from', () {
    final r = RecreateResult.fromJson({
      'origin': 'look',
      'inspired_by': 'usr_042',
      'pieces': [
        {
          'item_id': 'itm_425ac850a084',
          'category': 'top',
          'label': 'grey t-shirt',
          'color': 'grey',
          'color_hex': '#B3B2B0',
          'image': '/bo7/demo/photos/ds_top_29d44695.png',
        }
      ],
      'match_score': 1.0,
      'missing': [
        {'category': 'shoes', 'color_hex': '#222222'}
      ],
      'card': null,
      'sources': {'photo': null, 'match': 'mock'},
    });
    expect(r.pieces.single.toGarment().photoUrl, '/bo7/demo/photos/ds_top_29d44695.png');
    expect(r.missing, ['shoes']);
    expect(r.sources['match'], 'mock');
    expect(r.sources['photo'], 'n/a');
  });

  test('similar profiles (M5)', () {
    final p = SimilarProfile.fromJson({
      'user_id': 'yasmine',
      'name': 'Yasmine',
      'similarity': 0.537,
      'tags': ['traditional', 'local', 'bold'],
      'following': false,
    });
    expect(p.similarity, closeTo(0.537, 1e-9));
    expect(p.tags.first, 'traditional');
  });
}
