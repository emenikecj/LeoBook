// app_theme.dart: app_theme.dart: Widget/screen for App — Theme.
// Part of LeoBook App — Theme
//
// Classes: AppTheme

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../constants/app_colors.dart';
import 'liquid_glass_theme.dart';

class AppTheme {
  static ThemeData get darkTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: LiquidGlassTheme.bgGradientStart,
      primaryColor: AppColors.primary,
      cardColor: AppColors.glassDark,

      textTheme: GoogleFonts.lexendTextTheme().copyWith(
        displayLarge: GoogleFonts.lexend(
          fontSize: 22,
          fontWeight: FontWeight.w700,
          color: Colors.white,
          letterSpacing: -1.0,
        ),
        titleLarge: GoogleFonts.lexend(
          fontSize: 15,
          fontWeight: FontWeight.w600,
          color: Colors.white,
          letterSpacing: -0.3,
        ),
        titleMedium: GoogleFonts.lexend(
          fontSize: 13,
          fontWeight: FontWeight.w600,
          color: AppColors.textLight,
        ),
        bodyLarge: GoogleFonts.lexend(
          fontSize: 13,
          fontWeight: FontWeight.w400,
          color: AppColors.textLight,
          height: 1.5,
        ),
        bodyMedium: GoogleFonts.lexend(
          fontSize: 11,
          fontWeight: FontWeight.w400,
          color: AppColors.textGrey,
          height: 1.5,
        ),
        bodySmall: GoogleFonts.lexend(
          fontSize: 10,
          fontWeight: FontWeight.w400,
          color: AppColors.textGrey,
        ),
        labelLarge: GoogleFonts.lexend(
          fontSize: 9,
          fontWeight: FontWeight.w700,
          color: AppColors.textGrey,
          letterSpacing: 0.8,
        ),
      ),

      colorScheme: const ColorScheme.dark(
        primary: AppColors.primary,
        surface: AppColors.surfaceDark,
        onSurface: AppColors.textLight,
        error: AppColors.liveRed,
        secondary: AppColors.successGreen,
        surfaceContainerHighest: AppColors.surfaceDark,
      ),

      // Glass-aware AppBar
      appBarTheme: AppBarTheme(
        backgroundColor: AppColors.backgroundDark.withValues(alpha: 0.8),
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        titleTextStyle: GoogleFonts.lexend(
          color: Colors.white,
          fontSize: 15,
          fontWeight: FontWeight.w700,
          letterSpacing: -0.3,
        ),
      ),

      // Glass-aware Card theme
      cardTheme: CardThemeData(
        color: AppColors.glassDark,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: BorderSide(color: Colors.white.withValues(alpha: 0.05)),
        ),
      ),

      // Input Decoration
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.desktopSearchFill,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide.none,
        ),
        hintStyle: const TextStyle(
          color: Colors.white24,
          fontSize: 11,
          fontWeight: FontWeight.w500,
        ),
      ),

      // Smooth bottom sheet
      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: Colors.transparent,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
      ),

      // Animated snackbar
      snackBarTheme: SnackBarThemeData(
        backgroundColor: AppColors.cardDark,
        contentTextStyle: GoogleFonts.lexend(color: Colors.white, fontSize: 12),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        behavior: SnackBarBehavior.floating,
      ),

      // Floating action button
      floatingActionButtonTheme: FloatingActionButtonThemeData(
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),

      // Divider
      dividerColor: Colors.white10,
      dividerTheme: const DividerThemeData(
        color: Colors.white10,
        thickness: 0.5,
      ),
    );
  }
}
