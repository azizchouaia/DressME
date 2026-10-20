// Owner: BO7 (@bo7-owner) — entry screen of the BO7 tab (route /bo7_sharing in app/router.dart).
import 'package:flutter/material.dart';

import 'challenges_screen.dart';

/// BO7 hub: challenges (M15) + community feed, with the share studio (M10) in the app bar.
class FeedScreen extends StatelessWidget {
  const FeedScreen({super.key});

  @override
  Widget build(BuildContext context) => const ChallengesScreen();
}
