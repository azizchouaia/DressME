import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:avatar_studio/main.dart';

void main() {
  testWidgets('studio offers a photo build and a save', (tester) async {
    await tester.pumpWidget(const AvatarStudioApp());
    expect(find.text('Avatar Studio'), findsOneWidget);
    expect(find.text('Choose photo'), findsOneWidget);
    expect(find.text('Build sample'), findsOneWidget);
    expect(find.widgetWithText(OutlinedButton, 'Save GLB'), findsOneWidget);
  });
}
