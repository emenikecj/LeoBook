// app_colors.dart: ─── Brand ───────────────────────────────────────────────
// Part of LeoBook App — Constants
//
// Classes: AppColors

import 'package:flutter/material.dart';

class AppColors {
  // ─── Brand ───────────────────────────────────────────────
  // ─── Brand ───────────────────────────────────────────────
  static const Color primary = Color(0xFF137FEC);
  static const Color electricBlue = primary;

  // ─── Backgrounds ─────────────────────────────────────────
  static const Color backgroundLight = Color(0xFFF6F7F8);
  static const Color backgroundDark = Color(0xFF101922);
  static const Color surfaceDark = Color(0xFF182430);

  // ─── Desktop-Specific (Image Reference) ─────────────────
  static const Color desktopSidebarBg = Color(0xFF0D141C);
  static const Color desktopHeaderBg = Color(0xFF0F1720);
  static const Color desktopActiveIndicator = Color(0xFF137FEC);
  static const Color desktopSearchFill = Color(0xFF141F2B);

  // ─── Solid Card Tokens (Legacy Restoration) ──────────────
  static const Color cardDark = Color(0xFF182430);
  static const Color cardLight = Colors.white;

  // ─── Glass Tokens ────────────────────────────────────────
  static const Color glassDark = Color(0xFF182430);
  static const Color glassLight = Colors.white;
  static const Color glassBorderDark = Color(0xFF2C3E50);
  static const Color glassBorderLight = Color(0xFFE2E8F0);

  // ─── Liquid Glass Tokens ────────────────────────────────
  static const Color liquidGlassDark = Color(0xCC1A2332);
  static const Color liquidGlassLight = Color(0xCCFFFFFF);
  static const Color liquidGlassBorderDark = Color(0x1AFFFFFF);
  static const Color liquidGlassBorderLight = Color(0x33FFFFFF);
  static const Color liquidInnerGlow = Color(0x08FFFFFF);
  static const Color bgGradientStart = Color(0xFF0D1620);
  static const Color bgGradientEnd = Color(0xFF162232);

  // ─── States & Semantic ───────────────────────────────────
  static const Color liveRed = Color(0xFFFF3B30);
  static const Color successGreen = Color(0xFF34C759);
  static const Color accentBlue = Color(0xFF00D2FF);
  static const Color warning = Color(0xFFEAB308);
  static const Color success = successGreen;

  // ─── Text ────────────────────────────────────────────────
  static const Color textDark = Color(0xFF0F172A);
  static const Color textLight = Color(0xFFF1F5F9);
  static const Color textGrey = Color(0xFF64748B);
  static const Color textHint = Color(0xFF475569);

  // ─── Accents ─────────────────────────────────────────────
  static const Color aiPurple = Color(0xFF8B5CF6);
  static const Color accentYellow = Color(0xFFFFCC00);
}
