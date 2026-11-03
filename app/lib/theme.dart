import 'package:flutter/material.dart';

const paper = Color(0xFFF6F4F0);
const ink = Color(0xFF141414);
const inkSoft = Color(0xFF3B3935);
const muted = Color(0xFF8A857D);
const line = Color(0xFFE4DFD6);
const surface = Colors.white;
const danger = Color(0xFFB3261E);
const ok = Color(0xFF1F6F43);

ThemeData buildTheme() {
  final base = ThemeData(
    useMaterial3: true,
    scaffoldBackgroundColor: paper,
    colorScheme: const ColorScheme.light(
      primary: ink,
      onPrimary: paper,
      secondary: ink,
      surface: surface,
      error: danger,
      onSurface: ink,
    ),
    dividerColor: line,
  );
  return base.copyWith(
    textTheme: base.textTheme.apply(bodyColor: ink, displayColor: ink, fontFamily: 'Segoe UI'),
    appBarTheme: const AppBarTheme(
      backgroundColor: paper,
      foregroundColor: ink,
      elevation: 0,
      scrolledUnderElevation: 0,
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: ink,
        foregroundColor: paper,
        minimumSize: const Size.fromHeight(48),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: ink,
        minimumSize: const Size.fromHeight(48),
        side: const BorderSide(color: line),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(foregroundColor: inkSoft, minimumSize: const Size.fromHeight(44)),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: surface,
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: line)),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: line),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: ink, width: 1.4),
      ),
      labelStyle: const TextStyle(color: inkSoft),
      hintStyle: const TextStyle(color: muted),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: surface,
      indicatorColor: const Color(0xFFEFEBE4),
      labelTextStyle: WidgetStateProperty.resolveWith((states) {
        final selected = states.contains(WidgetState.selected);
        return TextStyle(fontSize: 12, color: selected ? ink : muted, fontWeight: selected ? FontWeight.w600 : FontWeight.w500);
      }),
      iconTheme: WidgetStateProperty.resolveWith((states) {
        return IconThemeData(color: states.contains(WidgetState.selected) ? ink : muted);
      }),
    ),
    cardTheme: CardThemeData(
      color: surface,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(24),
        side: const BorderSide(color: line),
      ),
      margin: EdgeInsets.zero,
    ),
  );
}
