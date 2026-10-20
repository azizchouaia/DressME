// BO7 · M15 — screens render from a fake repository (no server needed).
import 'package:dressme/features/bo7_sharing/data/challenge_models.dart';
import 'package:dressme/features/bo7_sharing/data/challenges_repository.dart';
import 'package:dressme/features/bo7_sharing/data/demo_wardrobe.dart';
import 'package:dressme/features/bo7_sharing/logic/challenges_providers.dart';
import 'package:dressme/features/bo7_sharing/ui/challenges_screen.dart';
import 'package:dressme/features/bo7_sharing/ui/widgets.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

const _challenge = Challenge(
  id: 'ch_7x7',
  title: '7 days, 7 outfits',
  description: 'A different outfit every day.',
  rules: [ChallengeRule('no_repeat', {})],
  durationDays: 7,
  tags: ['rotation'],
  participants: 12,
  joined: false,
  feasibility: 0.71,
  reason: 'Only 5 different outfits possible (shoes are the limit).',
);

class FakeRepo implements ChallengesRepository {
  @override
  Future<List<Challenge>> list(String userId, {bool recommended = true}) async => [_challenge];
  @override
  Future<Challenge> get(String challengeId, String userId) async => _challenge;
  @override
  Future<ChallengeProgress> join(String challengeId, String userId) async => _progress;
  @override
  Future<ChallengeProgress> progress(String challengeId, String userId) async => _progress;
  @override
  Future<EntryResult> submit(String challengeId, String userId, List<String> itemIds, {String? caption}) async =>
      EntryResult(day: 1, valid: true, violations: const [], suggestion: const [], progress: _progress);
  @override
  Future<List<LeaderboardRow>> leaderboard(String challengeId) async => const [];
  @override
  Future<List<ChallengePost>> posts({String? challengeId}) async => const [];
  @override
  Future<int> like(String postId, String userId) async => 1;
  @override
  Future<List<WardrobeItem>> wardrobe(String userId) async => demoWardrobe;
  @override
  String absoluteUrl(String path) => 'http://test$path';
}

const _progress = ChallengeProgress(
  challengeId: 'ch_7x7',
  durationDays: 7,
  daysLogged: 2,
  validDays: 1,
  streak: 0,
  completion: 0.14,
  points: 10,
  badges: ['Starter'],
  nextDay: 3,
  entries: [
    EntryView(day: 1, itemIds: ['a'], valid: true),
    EntryView(day: 2, itemIds: ['b'], valid: false, violations: ['x']),
  ],
);

void main() {
  testWidgets('challenge list shows title, duration and wardrobe fit', (tester) async {
    await tester.pumpWidget(ProviderScope(
      overrides: [challengesRepositoryProvider.overrideWithValue(FakeRepo())],
      child: const MaterialApp(home: ChallengesScreen()),
    ));
    await tester.pumpAndSettle();
    expect(find.text('7 days, 7 outfits'), findsOneWidget);
    expect(find.text('7 days'), findsOneWidget);
    expect(find.text('71%'), findsOneWidget);
    expect(find.textContaining('shoes are the limit'), findsOneWidget);
  });

  testWidgets('day strip shows valid, broken and next days', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: Scaffold(body: DayStrip(progress: _progress))));
    expect(find.byIcon(Icons.check), findsOneWidget);   // day 1
    expect(find.byIcon(Icons.close), findsOneWidget);   // day 2
    expect(find.text('3'), findsOneWidget);             // next day, not logged
    expect(find.text('7'), findsOneWidget);
  });
}
