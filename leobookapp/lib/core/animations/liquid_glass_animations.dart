// liquid_glass_animations.dart: Reusable fade-in + slide-up animation for staggered content loading.
// Part of LeoBook App — Animations
//
// Classes: LiquidFadeIn, _LiquidFadeInState

import 'package:flutter/material.dart';
import '../theme/liquid_glass_theme.dart';

/// Reusable fade-in + slide-up animation for staggered content loading.
class LiquidFadeIn extends StatefulWidget {
  final Widget child;
  final Duration delay;
  final Duration duration;
  final double slideOffset;

  const LiquidFadeIn({
    super.key,
    required this.child,
    this.delay = Duration.zero,
    this.duration = const Duration(milliseconds: 400),
    this.slideOffset = 20.0,
  });

  @override
  State<LiquidFadeIn> createState() => _LiquidFadeInState();
}

class _LiquidFadeInState extends State<LiquidFadeIn>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _opacity;
  late final Animation<Offset> _slide;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: widget.duration,
    );
    _opacity = CurvedAnimation(
      parent: _controller,
      curve: LiquidGlassTheme.menuPopInCurve,
    );
    _slide = Tween<Offset>(
      begin: Offset(0, widget.slideOffset / 100),
      end: Offset.zero,
    ).animate(CurvedAnimation(
      parent: _controller,
      curve: LiquidGlassTheme.menuPopInCurve,
    ));

    Future.delayed(widget.delay, () {
      if (mounted) _controller.forward();
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _opacity,
      child: SlideTransition(
        position: _slide,
        child: widget.child,
      ),
    );
  }
}

/// A bouncing scroll physics preset for lists.
const BouncingScrollPhysics liquidScrollPhysics = BouncingScrollPhysics(
  decelerationRate: ScrollDecelerationRate.fast,
);
