// glass_settings.dart: Performance-aware glass intensity toggle.
// Part of LeoBook App — Theme
//
// Classes: GlassSettings

import 'package:flutter/foundation.dart';

/// Performance-aware glass intensity toggle.
///
/// Controls whether BackdropFilter blur is active across the app.
/// When set to [GlassIntensity.none], glass containers fall back to
/// solid fills, eliminating GPU-expensive blur operations.
enum GlassIntensity {
  /// No blur — solid fills only. Best for low-end devices.
  none,

  /// Reduced blur radius (8px).
  medium,

  /// Full liquid glass effect (24px blur).
  full,
}

class GlassSettings {
  static final ValueNotifier<GlassIntensity> intensity =
      ValueNotifier(GlassIntensity.full);

  /// Returns blur sigma based on current intensity setting.
  static double get blurSigma {
    switch (intensity.value) {
      case GlassIntensity.none:
        return 0.0;
      case GlassIntensity.medium:
        return 8.0;
      case GlassIntensity.full:
        return 24.0;
    }
  }

  /// Whether blur is enabled at all.
  static bool get isBlurEnabled => intensity.value != GlassIntensity.none;
}
