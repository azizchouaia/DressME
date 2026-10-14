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
      int k = 24}) async {
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

    expect(find.text('jebba brodée'),
        findsOneWidget); // example chips before the first search

    await tester.enterText(find.byKey(const Key('bo6-query')),
        'baskets blanches à Tunis pour 80 TND');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pumpAndSettle();

    expect(repo.lastQuery, 'baskets blanches à Tunis pour 80 TND');
    expect(find.text('1 article trouvé'), findsOneWidget);
    expect(find.text('Baskets'), findsOneWidget);
    expect(find.text('≤ 80 TND'), findsOneWidget);
    expect(find.text('Basket à plateforme femme'), findsOneWidget);
    expect(find.text('69,3 TND'), findsOneWidget);
    expect(find.text('87 %'), findsOneWidget);
  });
}
