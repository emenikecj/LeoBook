// main_top_bar.dart: Responsive wrapper for the app's main top bar.
// Part of LeoBook App — Shared Widgets

import 'package:flutter/material.dart';
import 'package:leobookapp/core/constants/responsive_constants.dart';
import '../desktop/desktop_header.dart';
import '../../widgets/mobile/mobile_header.dart';

class MainTopBar extends StatelessWidget {
  final int currentIndex;
  final ValueChanged<int> onTabChanged;

  const MainTopBar({
    super.key,
    required this.currentIndex,
    required this.onTabChanged,
  });

  @override
  Widget build(BuildContext context) {
    if (Responsive.isDesktop(context)) {
      return DesktopHeader(
        currentIndex: currentIndex,
        onTabChanged: onTabChanged,
      );
    }
    return const MobileHeader();
  }
}
