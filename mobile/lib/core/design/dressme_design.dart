// DressMe design system: Flutter translation of the design prototype in docs/design/
// (colours, radii and text styles taken from the prototype's Tailwind classes).
// Use it in a screen with `Theme(data: dressMeTheme(), child: ...)` and the Dm* constants.
import 'package:flutter/cupertino.dart' show CupertinoPageTransitionsBuilder;
import 'package:flutter/material.dart';

/// Colours of the prototype, by role. The hex value in each comment is the Tailwind class used there.
abstract final class DmColors {
  // Dark surfaces and text
  static const ink =
      Color(0xFF211D19); // headers, primary buttons, selected chips
  static const inkDeep = Color(0xFF171512); // home hero, Studio background
  static const text = Color(0xFF1A1714); // main text on light backgrounds

  // Light surfaces
  static const page = Color(0xFFF6F3EE); // screen background
  static const canvas = Color(0xFFFAF9F7); // app shell background
  static const surface = Colors.white; // cards
  static const sand = Color(0xFFF4F0EA); // piece chips, small info blocks
  static const sandDark = Color(0xFFF0E8DD); // badges, round icon buttons

  // Gold accent
  static const gold =
      Color(0xFFC9A77B); // accent buttons, selected chips on dark
  static const goldLight = Color(0xFFE3C9A7); // accent text on dark
  static const bronze = Color(0xFF9A744B); // eyebrow labels on light
  static const bronzeDark = Color(0xFF8D6842); // links
  static const bar = Color(0xFFB78C5B); // progress bars, bullets

  // Lines and secondary text
  static const border = Color(0xFFE5DED4);
  static const borderStrong = Color(0xFFDED5C9);
  static const muted = Color(0xFF81776D); // captions
  static const mutedDark = Color(0xFF675F57); // secondary body text

  // States
  static const successBg = Color(0xFFEAF5EE);
  static const success = Color(0xFF4C9366);
  static const successDark = Color(0xFF214C31);
  static const warningBg = Color(0xFFFFF6E9);
  static const warning = Color(0xFF9A6733);
  static const ecoBg = Color(0xFFEFF7F1);
  static const eco = Color(0xFF5E9671);
}

/// Corner radii (Tailwind: rounded-xl 12, rounded-2xl 16, rounded-[24/28/30px], rounded-full).
abstract final class DmRadius {
  static const small = 12.0; // inputs inside cards, small blocks
  static const card = 16.0; // product cards, buttons
  static const panel = 24.0; // large sections
  static const hero = 28.0; // main card, bottom sheets
  static const pill = 100.0; // chips and tags
}

/// Fonts of the prototype (Google Fonts). Until they are bundled in pubspec.yaml,
/// Flutter falls back to the platform font with the same sizes and weights.
abstract final class DmFonts {
  static const serif = 'DM Serif Display'; // titles
  static const sans = 'DM Sans'; // everything else
}

/// Text styles used in the prototype.
abstract final class DmText {
  static const display = TextStyle(
      fontFamily: DmFonts.serif, fontSize: 34, height: 1, color: DmColors.text);
  static const title =
      TextStyle(fontFamily: DmFonts.serif, fontSize: 24, color: DmColors.ink);
  static const cardTitle =
      TextStyle(fontFamily: DmFonts.serif, fontSize: 19, color: DmColors.ink);

  /// Small uppercase label above a title ("SÉLECTION LOCALE"): write the text in capitals.
  static const eyebrow = TextStyle(
    fontFamily: DmFonts.sans,
    fontSize: 10,
    fontWeight: FontWeight.w700,
    letterSpacing: 1.8,
    color: DmColors.bronze,
  );
  static const body = TextStyle(
      fontFamily: DmFonts.sans,
      fontSize: 12,
      height: 1.5,
      color: DmColors.mutedDark);
  static const itemName = TextStyle(
      fontFamily: DmFonts.sans,
      fontSize: 12,
      fontWeight: FontWeight.w600,
      color: DmColors.ink);
  static const caption =
      TextStyle(fontFamily: DmFonts.sans, fontSize: 10, color: DmColors.muted);
  static const price = TextStyle(
      fontFamily: DmFonts.sans,
      fontSize: 11,
      fontWeight: FontWeight.w700,
      color: DmColors.text);
  static const button = TextStyle(
      fontFamily: DmFonts.sans, fontSize: 13, fontWeight: FontWeight.w600);
}

/// Material theme matching the prototype: beige page, white bordered cards, pill chips,
/// dark primary buttons, gold accent, rounded bottom sheets.
ThemeData dressMeTheme() {
  const scheme = ColorScheme.light(
    primary: DmColors.ink,
    onPrimary: Colors.white,
    secondary: DmColors.gold,
    onSecondary: DmColors.inkDeep,
    surface: DmColors.surface,
    onSurface: DmColors.text,
    onSurfaceVariant: DmColors.muted,
    outline: DmColors.borderStrong,
    outlineVariant: DmColors.border,
    surfaceContainerHighest: DmColors.sand,
  );
  final cardShape = RoundedRectangleBorder(
    borderRadius: BorderRadius.circular(DmRadius.card),
    side: const BorderSide(color: DmColors.border),
  );
  final buttonShape = RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(DmRadius.card));
  return ThemeData(
    // pushed screens (piece form, sheets...) zoom in softly on every platform
    pageTransitionsTheme: const PageTransitionsTheme(builders: {
      TargetPlatform.android: ZoomPageTransitionsBuilder(),
      TargetPlatform.iOS: CupertinoPageTransitionsBuilder(),
      TargetPlatform.windows: ZoomPageTransitionsBuilder(),
      TargetPlatform.macOS: CupertinoPageTransitionsBuilder(),
      TargetPlatform.linux: ZoomPageTransitionsBuilder(),
      TargetPlatform.fuchsia: ZoomPageTransitionsBuilder(),
    }),
    useMaterial3: true,
    colorScheme: scheme,
    fontFamily: DmFonts.sans,
    scaffoldBackgroundColor: DmColors.page,
    appBarTheme: const AppBarTheme(
      backgroundColor: DmColors.page,
      foregroundColor: DmColors.ink,
      elevation: 0,
      scrolledUnderElevation: 0,
      titleTextStyle: DmText.title,
    ),
    cardTheme: CardThemeData(
        color: DmColors.surface,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: cardShape),
    chipTheme: const ChipThemeData(
      backgroundColor: DmColors.surface,
      selectedColor: DmColors.ink,
      labelStyle: TextStyle(
          fontSize: 11, fontWeight: FontWeight.w600, color: DmColors.mutedDark),
      secondaryLabelStyle: TextStyle(
          fontSize: 11, fontWeight: FontWeight.w600, color: Colors.white),
      side: BorderSide(color: DmColors.borderStrong),
      shape: StadiumBorder(),
      showCheckmark: false,
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: DmColors.ink,
        foregroundColor: Colors.white,
        textStyle: DmText.button,
        padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 20),
        shape: buttonShape,
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: DmColors.ink,
        side: const BorderSide(color: DmColors.borderStrong),
        textStyle: DmText.button,
        padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 20),
        shape: buttonShape,
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: DmColors.bronzeDark,
        textStyle: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: DmColors.surface,
      hintStyle: const TextStyle(fontSize: 12, color: DmColors.muted),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(DmRadius.card),
        borderSide: const BorderSide(color: DmColors.borderStrong),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(DmRadius.card),
        borderSide: const BorderSide(color: DmColors.borderStrong),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(DmRadius.card),
        borderSide: const BorderSide(color: DmColors.ink, width: 1.4),
      ),
    ),
    bottomSheetTheme: const BottomSheetThemeData(
      backgroundColor: DmColors.page,
      shape: RoundedRectangleBorder(
          borderRadius:
              BorderRadius.vertical(top: Radius.circular(DmRadius.hero))),
    ),
    snackBarTheme: SnackBarThemeData(
      backgroundColor: DmColors.ink,
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(DmRadius.pill)),
    ),
    progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: DmColors.bar, linearTrackColor: Color(0xFFEEE8E0)),
    dividerTheme:
        const DividerThemeData(color: Color(0xFFEEE8E0), thickness: 1),
  );
}

/// Eyebrow label + serif title, the section header used on every prototype screen.
class DmSectionHeader extends StatelessWidget {
  const DmSectionHeader(
      {super.key, required this.eyebrow, required this.title, this.trailing});

  final String eyebrow;
  final String title;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(eyebrow.toUpperCase(), style: DmText.eyebrow),
              const SizedBox(height: 2),
              Text(title, style: DmText.title),
            ],
          ),
        ),
        if (trailing != null) trailing!,
      ],
    );
  }
}

/// Small rounded tag ("92 % style", "Marque tunisienne").
class DmPill extends StatelessWidget {
  const DmPill(this.label, {super.key, this.dark = false});

  final String label;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: dark ? DmColors.ink.withValues(alpha: 0.8) : DmColors.sand,
        borderRadius: BorderRadius.circular(DmRadius.pill),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w600,
          color: dark ? Colors.white : DmColors.mutedDark,
        ),
      ),
    );
  }
}
