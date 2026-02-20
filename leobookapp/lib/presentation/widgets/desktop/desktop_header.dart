// desktop_header.dart: desktop_header.dart: Widget/screen for App — Responsive Widgets.
// Part of LeoBook App — Responsive Widgets
//
// Classes: DesktopHeader

import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/theme/liquid_glass_theme.dart';
import '../../../logic/cubit/search_cubit.dart';
import '../../screens/search_screen.dart';

class DesktopHeader extends StatelessWidget {
  final int currentIndex;
  final ValueChanged<int> onTabChanged;

  const DesktopHeader({
    super.key,
    required this.currentIndex,
    required this.onTabChanged,
  });

  @override
  Widget build(BuildContext context) {
    return ClipRect(
      child: BackdropFilter(
        filter: ImageFilter.blur(
          sigmaX: LiquidGlassTheme.blurRadiusMedium,
          sigmaY: LiquidGlassTheme.blurRadiusMedium,
        ),
        child: Container(
          height: 80,
          padding: const EdgeInsets.symmetric(horizontal: 32),
          decoration: BoxDecoration(
            color: AppColors.backgroundDark.withValues(alpha: 0.35),
            border: const Border(bottom: BorderSide(color: Colors.white10)),
          ),
          child: Row(
            children: [
              // Brand
              const Text(
                "LEOBOOK",
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w900,
                  color: Colors.white,
                  letterSpacing: 2.0,
                ),
              ),
              const SizedBox(width: 24),
              // Search Bar
              Expanded(
                flex: 2,
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 500),
                  child: GestureDetector(
                    onTap: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => BlocProvider.value(
                            value: context.read<SearchCubit>(),
                            child: const SearchScreen(),
                          ),
                        ),
                      );
                    },
                    child: AbsorbPointer(
                      child: TextField(
                        readOnly: true,
                        style: const TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: Colors.white,
                        ),
                        decoration: InputDecoration(
                          hintText: "SEARCH MATCHES, TEAMS OR LEAGUES...",
                          hintStyle: const TextStyle(
                            color: Colors.white24,
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                            letterSpacing: 1.2,
                          ),
                          prefixIcon: const Icon(
                            Icons.search_rounded,
                            color: Colors.white38,
                            size: 22,
                          ),
                          filled: true,
                          fillColor: AppColors.desktopSearchFill,
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(16),
                            borderSide: BorderSide.none,
                          ),
                          contentPadding:
                              const EdgeInsets.symmetric(vertical: 0),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
              const Spacer(),
              // Navigation Items (mirrors mobile bottom nav)
              Row(
                children: [
                  _buildNavButton(
                      Icons.home_rounded, Icons.home_outlined, 0, "HOME"),
                  const SizedBox(width: 8),
                  _buildNavButton(Icons.science_rounded, Icons.science_outlined,
                      1, "RULES"),
                  const SizedBox(width: 8),
                  _buildNavButton(Icons.emoji_events_rounded,
                      Icons.emoji_events_outlined, 2, "TOP"),
                  const SizedBox(width: 16),
                  _buildIconButton(Icons.notifications_none_rounded),
                  const SizedBox(width: 16),
                  Container(width: 1, height: 32, color: Colors.white10),
                  const SizedBox(width: 24),
                  _buildBalance(),
                  const SizedBox(width: 16),
                  _buildAvatar(),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildNavButton(
    IconData activeIcon,
    IconData inactiveIcon,
    int index,
    String label,
  ) {
    final isSelected = currentIndex == index;
    return GestureDetector(
      onTap: () => onTabChanged(index),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: isSelected
              ? AppColors.primary.withValues(alpha: 0.15)
              : Colors.transparent,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              isSelected ? activeIcon : inactiveIcon,
              size: 18,
              color: isSelected ? AppColors.primary : Colors.white38,
            ),
            const SizedBox(width: 6),
            Text(
              label,
              style: TextStyle(
                fontSize: 11,
                fontWeight: isSelected ? FontWeight.w900 : FontWeight.w600,
                color: isSelected ? AppColors.primary : Colors.white38,
                letterSpacing: 0.8,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildIconButton(IconData icon) {
    return Container(
      width: 44,
      height: 44,
      decoration: BoxDecoration(
        color: AppColors.desktopSearchFill,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Center(child: Icon(icon, color: Colors.white54, size: 22)),
    );
  }

  Widget _buildBalance() {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Text(
          "BALANCE",
          style: TextStyle(
            fontSize: 10,
            fontWeight: FontWeight.w900,
            color: Colors.white.withValues(alpha: 0.3),
            letterSpacing: 1.5,
          ),
        ),
        const Text(
          "₦12,450.00",
          style: TextStyle(
            fontSize: 15,
            fontWeight: FontWeight.w900,
            color: Colors.white,
          ),
        ),
      ],
    );
  }

  Widget _buildAvatar() {
    return Container(
      width: 48,
      height: 48,
      padding: const EdgeInsets.all(2),
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        border: Border.all(color: Colors.white10, width: 1),
      ),
      child: const Center(
        child: Icon(
          Icons.person_rounded,
          color: Colors.white24,
          size: 24,
        ),
      ),
    );
  }
}
