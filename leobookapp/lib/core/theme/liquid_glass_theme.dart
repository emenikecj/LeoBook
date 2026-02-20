// liquid_glass_theme.dart: Central constants for the Liquid Glass design system.
// Part of LeoBook App — Theme
//
// Classes: LiquidGlassTheme

import 'package:flutter/material.dart';

/// Central constants for the Liquid Glass design system.
/// Inspired by Telegram's 2026 "Liquid Glass" aesthetic.
class LiquidGlassTheme {
  // ─── Blur ──────────────────────────────────────────────
  static const double blurRadius = 24.0;
  static const double blurRadiusMedium = 16.0;
  static const double blurRadiusLight = 8.0;

  // ─── Opacity ───────────────────────────────────────────
  static const double opacity = 0.75;
  static const double opacityMedium = 0.55;
  static const double opacityLight = 0.35;

  // ─── Shape ─────────────────────────────────────────────
  static const double borderRadius = 20.0;
  static const double borderRadiusSmall = 12.0;
  static const double borderRadiusLarge = 28.0;
  static const double borderWidth = 1.0;

  // ─── Glass Fill Colors ─────────────────────────────────
  static const Color glassLight = Color(0xCCFFFFFF);
  static const Color glassDark = Color(0xCC1A2332);
  static const Color glassBorderLight = Color(0x33FFFFFF);
  static const Color glassBorderDark = Color(0x1AFFFFFF);

  // ─── Refraction / Inner Glow ───────────────────────────
  static const Color innerGlowLight = Color(0x0DFFFFFF);
  static const Color innerGlowDark = Color(0x08FFFFFF);

  // ─── Background Gradient ───────────────────────────────
  static const Color bgGradientStart = Color(0xFF0D1620);
  static const Color bgGradientEnd = Color(0xFF162232);

  // ─── Animation Curves ──────────────────────────────────
  static const Curve tabSwitchCurve = Curves.easeInOutQuad;
  static const Duration tabSwitchDuration = Duration(milliseconds: 300);

  static const Curve menuPopInCurve = Curves.easeOutExpo;
  static const Duration menuPopInDuration = Duration(milliseconds: 400);

  static const Curve cardPressCurve = Curves.easeOutCubic;
  static const Duration cardPressDuration = Duration(milliseconds: 200);

  // ─── Helpers ───────────────────────────────────────────
  static Color glassColor(Brightness brightness) =>
      brightness == Brightness.dark ? glassDark : glassLight;

  static Color glassBorder(Brightness brightness) =>
      brightness == Brightness.dark ? glassBorderDark : glassBorderLight;

  static Color innerGlow(Brightness brightness) =>
      brightness == Brightness.dark ? innerGlowDark : innerGlowLight;

  static LinearGradient backgroundGradient() => const LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [bgGradientStart, bgGradientEnd],
      );
}
