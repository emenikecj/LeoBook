// responsive_constants.dart: Responsive layout constants and utilities for LeoBook.
// Part of LeoBook App — Constants
//
// Classes: Responsive

library;

import 'package:flutter/material.dart';

class Responsive {
  Responsive._();

  // ── Breakpoints ──
  static const double breakpointMobile = 600;
  static const double breakpointTablet = 900;
  static const double breakpointDesktop = 1024;
  static const double breakpointWide = 1400;

  // ── Reference width (iPhone SE = 375) ──
  static const double _ref = 375;

  /// Scale-proportional value. Returns [baseValue] scaled to current viewport.
  /// On a 375dp-wide screen, returns exactly [baseValue].
  /// On larger screens, scales up (clamped at 1.6x).
  /// On smaller screens, scales down (clamped at 0.65x).
  static double sp(BuildContext context, double baseValue) {
    final w = MediaQuery.sizeOf(context).width;
    final scale = (w / _ref).clamp(0.65, 1.6);
    return baseValue * scale;
  }

  /// Like [sp] but for desktop-aware layouts (uses 1440 as desktop ref).
  static double dp(BuildContext context, double baseValue) {
    final w = MediaQuery.sizeOf(context).width;
    if (w >= breakpointDesktop) {
      // On desktop, scale relative to 1440 reference
      final scale = (w / 1440).clamp(0.7, 1.3);
      return baseValue * scale;
    }
    return sp(context, baseValue);
  }

  // ── Horizontal Page Padding ──
  static double horizontalPadding(BuildContext context) {
    final w = MediaQuery.sizeOf(context).width;
    if (w > breakpointDesktop) return sp(context, 24);
    if (w > breakpointTablet) return sp(context, 16);
    return sp(context, 10);
  }

  // ── Horizontal-Scroll Card Width ──
  static double cardWidth(double availableWidth,
      {double minWidth = 160, double maxWidth = 300}) {
    final w = availableWidth * 0.28;
    return w.clamp(minWidth, maxWidth);
  }

  // ── Horizontal-Scroll List Height ──
  static double listHeight(double availableWidth,
      {double min = 120, double max = 200}) {
    final h = availableWidth * 0.12;
    return h.clamp(min, max);
  }

  // ── Bottom Nav Margin (mobile-only) ──
  static EdgeInsets bottomNavMargin(BuildContext context) {
    final w = MediaQuery.sizeOf(context).width;
    final horizontal = (w * 0.04).clamp(16.0, 40.0);
    final bottom = (w * 0.025).clamp(8.0, 20.0);
    return EdgeInsets.fromLTRB(horizontal, 0, horizontal, bottom);
  }

  // ── Helpers ──
  static bool isMobile(BuildContext context) =>
      MediaQuery.sizeOf(context).width < breakpointTablet;
  static bool isTablet(BuildContext context) {
    final w = MediaQuery.sizeOf(context).width;
    return w >= breakpointTablet && w < breakpointDesktop;
  }

  static bool isDesktop(BuildContext context) =>
      MediaQuery.sizeOf(context).width >= breakpointDesktop;
}
