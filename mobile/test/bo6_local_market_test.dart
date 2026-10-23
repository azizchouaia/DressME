// Owner: BO6 — BO6 screen with a fake M7 repository (no server, no network).
import 'package:dressme/features/bo6_local_market/data/bo6_local_market_repository.dart';
import 'package:dressme/features/bo6_local_market/logic/bo6_local_market_provider.dart';
import 'package:dressme/features/bo6_local_market/ui/bo6_local_market_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class _FakeRepository extends LocalMarketRepository {
  String? lastQuery;
  String? lastCity;

  @override
  Future<LocalSearchResult> search(
      {required String query,
      String? city,
      double? maxPriceTnd,
      String? gender,
      String? sessionId,
      int k = 24,
      int offset = 0}) async {
    lastQuery = query;
    lastCity = city;
    return const LocalSearchResult(
      totalMatches: 1,
      parsed: ParsedQuery(
          subcategory: 'sneakers',
          color: 'white',
          maxPriceTnd: 80,
          city: 'Tunis'),
      results: [
        LocalProduct(
          productId: 'prd_2b7db627f3',
          shop: 'Manuella',
          area: 'Tunis',
          item: 'Basket à plateforme femme',
          priceTnd: 69.3,
          match: 0.87,
          category: 'shoes',
          subcategory: 'sneakers',
          imageUrl: 'https://example.invalid/basket.jpg',
          productUrl: 'https://manuella.com.tn/products/basket',
          shopUrl: 'https://manuella.com.tn',
          originType: 'local_brand',
          available: true,
          reasons: [
            'Baskets',
            'Couleur : blanc',
            '69.3 TND (budget 80 TND)',
            'Boutique à Tunis'
          ],
        ),
      ],
    );
  }
}

/// 30 dresses served page by page, like M7 with `offset`.
class _PagedRepository extends LocalMarketRepository {
  final offsets = <int>[];

  @override
  Future<LocalSearchResult> search(
      {required String query,
      String? city,
      double? maxPriceTnd,
      String? gender,
      String? sessionId,
      int k = 24,
      int offset = 0}) async {
    offsets.add(offset);
    final end = (offset + k) > 30 ? 30 : offset + k;
    return LocalSearchResult(
      totalMatches: 30,
      parsed: const ParsedQuery(subcategory: 'dress'),
      results: [
        for (var i = offset; i < end; i++)
          LocalProduct(
            productId: 'prd_$i',
            shop: 'HA',
            item: 'Robe $i',
            priceTnd: 49.99,
            match: 0.9,
            category: 'dress',
            subcategory: 'dress',
            imageUrl: 'https://example.invalid/$i.jpg',
            productUrl: 'https://ha.com.tn/p/$i',
            shopUrl: 'https://ha.com.tn',
            originType: 'local_brand',
            available: true,
          ),
      ],
    );
  }
}

/// Jeans for both genders: the agent asks "For women or for men?", then applies the answer.
class _AskingRepository extends LocalMarketRepository {
  final answers = <String>[];
  String? session;

  static LocalProduct _jean(String id, String item) => LocalProduct(
        productId: id,
        shop: 'Ms. Marion',
        item: item,
        priceTnd: 79,
        match: 0.9,
        category: 'bottom',
        subcategory: 'jeans',
        imageUrl: 'https://example.invalid/$id.jpg',
        productUrl: 'https://example.invalid/p/$id',
        shopUrl: 'https://example.invalid',
        originType: 'local_brand',
        available: true,
      );

  @override
  Future<LocalSearchResult> search(
      {required String query,
      String? city,
      double? maxPriceTnd,
      String? gender,
      String? sessionId,
      int k = 24,
      int offset = 0}) async {
    session = sessionId;
    return LocalSearchResult(
      totalMatches: 2,
      parsed: const ParsedQuery(subcategory: 'jeans'),
      question: 'For women or for men?',
      questionKey: 'gender',
      results: [_jean('w1', 'Jean femme'), _jean('m1', 'Jean homme')],
    );
  }

  @override
  Future<LocalSearchResult> answer(
      {required String sessionId,
      required String questionKey,
      required String value}) async {
    answers.add('$sessionId $questionKey=$value');
    return LocalSearchResult(
      totalMatches: 1,
      parsed: const ParsedQuery(subcategory: 'jeans', gender: 'women'),
      memoryNotes: const [
        'Your answer “women” is applied to your previous search.'
      ],
      results: [_jean('w1', 'Jean femme')],
    );
  }
}

void main() {
  test('formatTnd uses the Tunisian dinar and a decimal comma', () {
    expect(formatTnd(69.3), '69,3 TND');
    expect(formatTnd(75), '75 TND');
    expect(formatTnd(62.65), '62,65 TND');
  });

  test('shortArea keeps one city and counts the others', () {
    expect(shortArea('Sousse'), 'Sousse');
    expect(shortArea('Tunis; La Soukra; Sousse'), 'Tunis +2');
  });

  testWidgets('search shows the understood filters and the local pieces',
      (tester) async {
    final repo = _FakeRepository();
    await tester.pumpWidget(ProviderScope(
      overrides: [localMarketRepositoryProvider.overrideWithValue(repo)],
      child: const MaterialApp(home: LocalMarketScreen()),
    ));

    expect(find.text('embroidered jebba'),
        findsOneWidget); // example chips before the first search

    await tester.enterText(find.byKey(const Key('bo6-query')),
        'white sneakers in Tunis for 80 TND');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pumpAndSettle();

    expect(repo.lastQuery, 'white sneakers in Tunis for 80 TND');
    expect(find.text('1 piece found'), findsOneWidget);
    expect(find.text('Sneakers'), findsOneWidget);
    expect(find.text('≤ 80 TND'), findsOneWidget);
    expect(find.text('Basket à plateforme femme'), findsOneWidget);
    expect(find.text('69,3 TND'), findsOneWidget);
    expect(find.text('87 %'), findsOneWidget);
    expect(find.textContaining('more'), findsNothing); // everything shown
  });

  testWidgets('"Show more" loads the next page of the same search',
      (tester) async {
    final repo = _PagedRepository();
    await tester.pumpWidget(ProviderScope(
      overrides: [localMarketRepositoryProvider.overrideWithValue(repo)],
      child: const MaterialApp(home: LocalMarketScreen()),
    ));
    await tester.enterText(find.byKey(const Key('bo6-query')), 'robe');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pumpAndSettle();
    expect(find.text('30 pieces found · 24 shown'), findsOneWidget);

    final more = find.text('Show 6 more');
    await tester.scrollUntilVisible(more, 300,
        scrollable: find.byType(Scrollable).last);
    await tester.ensureVisible(more);
    await tester.pumpAndSettle();
    await tester.tap(more);
    await tester.pumpAndSettle();

    expect(repo.offsets, [0, 24]); // second call starts after the first page
    expect(find.textContaining(' more'), findsNothing); // all 30 are shown
    await tester.scrollUntilVisible(find.text('Robe 29'), 300,
        scrollable: find.byType(Scrollable).last);
    expect(find.text('Robe 29'), findsOneWidget); // last piece of page 2
  });

  testWidgets(
      'the agent asks for women or men and the answer is applied to the same search',
      (tester) async {
    final repo = _AskingRepository();
    await tester.pumpWidget(ProviderScope(
      overrides: [localMarketRepositoryProvider.overrideWithValue(repo)],
      child: const MaterialApp(home: LocalMarketScreen()),
    ));
    await tester.enterText(find.byKey(const Key('bo6-query')), 'jean');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pumpAndSettle();

    expect(find.text('For women or for men?'), findsOneWidget);
    await tester.tap(find.text('Women'));
    await tester.pumpAndSettle();

    expect(repo.answers,
        ['${repo.session} gender=women']); // same session, request not repeated
    expect(find.text('For women or for men?'), findsNothing);
    expect(find.text('Jean homme'), findsNothing);
    expect(
        find.textContaining('applied to your previous search'), findsOneWidget);
    expect(find.text('Forget my answers'), findsOneWidget);
  });
}
