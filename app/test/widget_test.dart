import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:smart_wardrobe/router.dart';
import 'package:smart_wardrobe/state.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('signed-out visitors see the welcome screen', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final preferences = await SharedPreferences.getInstance();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [sharedPreferencesProvider.overrideWithValue(preferences)],
        child: const SmartWardrobeApp(),
      ),
    );
    expect(find.text('Your real clothes, on your own avatar.'), findsOneWidget);
    expect(find.text('Explore the demo wardrobe'), findsOneWidget);
  });
}
