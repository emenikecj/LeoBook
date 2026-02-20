// glass_container.dart: glass_container.dart: Widget/screen for App — Core Widgets.
// Part of LeoBook App — Core Widgets
//
// Classes: GlassContainer, _GlassContainerState

import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../constants/app_colors.dart';
import '../theme/liquid_glass_theme.dart';
import '../theme/glass_settings.dart';

/// Premium frosted-glass container with Telegram-inspired Liquid Glass aesthetics.
///
/// Features:
/// - Configurable backdrop blur (respects performance settings)
/// - Inner glow gradient for depth / refraction illusion
/// - Hover (scale up) and press (scale down) micro-animations
/// - Optional radial refraction shimmer via ShaderMask
/// - More translucent by default (~60% opacity) for see-through effect
class GlassContainer extends StatefulWidget {
  final Widget child;
  final double borderRadius;
  final EdgeInsetsGeometry? padding;
  final EdgeInsetsGeometry? margin;
  final double blurSigma;
  final Color? color;
  final Color? borderColor;
  final double borderWidth;
  final VoidCallback? onTap;
  final bool interactive;
  final bool enableRefraction;

  const GlassContainer({
    super.key,
    required this.child,
    this.borderRadius = 12,
    this.padding,
    this.margin,
    this.blurSigma = 16,
    this.color,
    this.borderColor,
    this.borderWidth = 0.5,
    this.onTap,
    this.interactive = true,
    this.enableRefraction = false,
  });

  @override
  State<GlassContainer> createState() => _GlassContainerState();
}

class _GlassContainerState extends State<GlassContainer> {
  bool _isHovered = false;
  bool _isPressed = false;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    // More translucent default: 0x99 = 60% opacity for Telegram-like see-through
    Color fillColor = widget.color ??
        (isDark
            ? const Color(0x991A2332) // 60% dark glass
            : const Color(0x99FFFFFF)); // 60% light glass
    Color border = widget.borderColor ??
        (isDark
            ? AppColors.liquidGlassBorderDark
            : AppColors.liquidGlassBorderLight);

    // Adjust for states if interactive
    double scale = 1.0;
    if (widget.interactive && widget.onTap != null) {
      if (_isPressed) {
        scale = 0.98;
        fillColor = fillColor.withValues(
          alpha: (fillColor.a * 1.15).clamp(0.0, 1.0),
        );
      } else if (_isHovered) {
        scale = 1.01;
        fillColor = fillColor.withValues(
          alpha: (fillColor.a * 1.08).clamp(0.0, 1.0),
        );
      }
    }

    final glassDecoration = BoxDecoration(
      color: fillColor,
      borderRadius: BorderRadius.circular(widget.borderRadius),
      border: Border.all(
        color: _isHovered ? AppColors.primary.withValues(alpha: 0.25) : border,
        width: widget.borderWidth,
      ),
      boxShadow: [
        // Inner glow for depth
        BoxShadow(
          color: LiquidGlassTheme.innerGlow(Theme.of(context).brightness),
          blurRadius: 1,
          spreadRadius: 0,
          offset: const Offset(0, 0.5),
        ),
        // Outer subtle shadow on hover
        if (_isHovered)
          BoxShadow(
            color: AppColors.primary.withValues(alpha: 0.08),
            blurRadius: 12,
            spreadRadius: 1,
          ),
      ],
    );

    Widget glassChild = AnimatedContainer(
      duration: LiquidGlassTheme.cardPressDuration,
      padding: widget.padding,
      decoration: glassDecoration,
      child: widget.child,
    );

    // Refraction shimmer — subtle radial gradient overlay
    if (widget.enableRefraction) {
      glassChild = ShaderMask(
        shaderCallback: (bounds) => RadialGradient(
          center: const Alignment(-0.8, -0.8),
          radius: 1.5,
          colors: [
            Colors.white.withValues(alpha: 0.04),
            Colors.transparent,
            Colors.white.withValues(alpha: 0.02),
          ],
          stops: const [0.0, 0.5, 1.0],
        ).createShader(bounds),
        blendMode: BlendMode.srcOver,
        child: glassChild,
      );
    }

    return MouseRegion(
      onEnter: (_) => setState(() => _isHovered = true),
      onExit: (_) => setState(() => _isHovered = false),
      child: GestureDetector(
        onTapDown: (_) => setState(() => _isPressed = true),
        onTapUp: (_) => setState(() => _isPressed = false),
        onTapCancel: () => setState(() => _isPressed = false),
        onTap: () {
          if (widget.onTap != null) {
            HapticFeedback.lightImpact();
            widget.onTap!();
          }
        },
        child: AnimatedScale(
          scale: scale,
          duration: LiquidGlassTheme.cardPressDuration,
          curve: LiquidGlassTheme.cardPressCurve,
          child: Container(
            margin: widget.margin,
            child: Builder(
              builder: (context) {
                final sigma =
                    GlassSettings.isBlurEnabled ? GlassSettings.blurSigma : 0.0;
                final inner = ClipRRect(
                  borderRadius: BorderRadius.circular(widget.borderRadius),
                  child: sigma > 0
                      ? BackdropFilter(
                          filter: ImageFilter.blur(
                            sigmaX: sigma,
                            sigmaY: sigma,
                          ),
                          child: glassChild,
                        )
                      : glassChild,
                );
                return inner;
              },
            ),
          ),
        ),
      ),
    );
  }
}
