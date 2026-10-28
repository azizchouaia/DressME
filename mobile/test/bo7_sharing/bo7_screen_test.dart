// Owner: BO7 — the four tabs open with data from a fake repository (no server needed).
import 'package:dressme/features/bo7_sharing/data/bo7_api.dart';
import 'package:dressme/features/bo7_sharing/data/bo7_models.dart';
import 'package:dressme/features/bo7_sharing/data/bo7_repository.dart';
import 'package:dressme/features/bo7_sharing/logic/bo7_providers.dart';
import 'package:dressme/features/bo7_sharing/ui/bo7_sharing_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class _FakeRepository extends Bo7Repository {
  _FakeRepository() : super(Bo7Api());

  @override
  Future<List<Garment>> wardrobe(String userId) async => const [
        Garment(id: 'a', name: 'white shirt', category: 'top', colorHex: '#FFFFFF', color: 'white'),
        Garment(id: 'b', name: 'black jeans', category: 'bottom', colorHex: '#111111', color: 'black'),
        Garment(id: 'c', name: 'balgha', category: 'shoes', colorHex: '#AA2222', localTag: 'Medina artisans'),
      ];

  @override
  Future<List<Challenge>> challenges(String userId) async => [
        Challenge.fromJson({
          'challenge_id': 'ch_mono',
          'title': 'Monochrome week',
          'description': 'Five days in black, white and grey only.',
          'rules': [
            {'type': 'no_repeat', 'params': {}},
          ],
          'duration_days': 5,
          'participants': 2,
          'feasibility': 0.8,
        }),
      ];

  @override
  Future<List<Post>> posts({String? challengeId}) async => const [];

  @override
  Future<List<Shop>> shops() async => const [Shop(name: 'Cravate', kind: 'Tunisian shop')];

  @override
  Future<ShareMetrics> metrics({String? userId}) async => ShareMetrics.fromJson({'cards': 0, 'k_factor': 0});

  @override
  Future<List<Ambassador>> ambassadors() async => const [];
}

void main() {
  testWidgets('Défis, Communauté, Studio and Garde-robe tabs', (tester) async {
    tester.view.physicalSize = const Size(1200, 2400);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [bo7RepositoryProvider.overrideWithValue(_FakeRepository())],
        child: const MaterialApp(home: FeedScreen()),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Tes défis'), findsOneWidget);
    expect(find.text('Monochrome week'), findsOneWidget);
    expect(find.text('80 %'), findsOneWidget);

    await tester.tap(find.text('Communauté'));
    await tester.pumpAndSettle();
    expect(find.text('Pas encore de publication'), findsOneWidget);

    await tester.tap(find.text('Studio'));
    await tester.pumpAndSettle();
    expect(find.text('Partager mon look'), findsOneWidget);
    expect(find.text('Sur mon avatar'), findsOneWidget);

    await tester.tap(find.text('Garde-robe').last);
    await tester.pumpAndSettle();
    expect(find.text('Ma garde-robe'), findsOneWidget);
    expect(find.text('Ouvrir'), findsOneWidget);
  });
}
