// main_screen.dart: main_screen.dart: Widget/screen for App — Screens.
// Part of LeoBook App — Screens
//
// Classes: MainScreen, _MainScreenState

import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:leobookapp/core/constants/app_colors.dart';

import 'package:leobookapp/core/constants/responsive_constants.dart';
import 'package:leobookapp/presentation/screens/home_screen.dart';
import 'package:leobookapp/presentation/screens/account_screen.dart';
import 'package:leobookapp/presentation/screens/rule_engine/backtest_dashboard.dart';
import 'package:leobookapp/presentation/screens/top_predictions_screen.dart';
import 'package:leobookapp/presentation/widgets/desktop/desktop_header.dart';
import 'package:leobookapp/logic/cubit/search_cubit.dart';
import 'package:leobookapp/logic/cubit/home_cubit.dart';
import 'package:leobookapp/data/models/match_model.dart';

class MainScreen extends StatefulWidget {
  const MainScreen({super.key});

  @override
  State<MainScreen> createState() => _MainScreenState();
}

class _MainScreenState extends State<MainScreen> {
  int _currentIndex = 0;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return LayoutBuilder(
      builder: (context, constraints) {
        final isDesktop = constraints.maxWidth > 1024;

        return BlocBuilder<HomeCubit, HomeState>(
          builder: (context, state) {
            Widget bodyArea;

            if (state is HomeLoaded) {
              final content = Column(
                children: [
                  if (isDesktop)
                    DesktopHeader(
                      currentIndex: _currentIndex,
                      onTabChanged: (i) => setState(() => _currentIndex = i),
                    ),
                  Expanded(
                    child: IndexedStack(
                      index: _currentIndex,
                      children: [
                        HomeScreen(
                          onViewAllPredictions: () =>
                              setState(() => _currentIndex = 2),
                        ),
                        const BacktestDashboard(),
                        const TopPredictionsScreen(),
                        const AccountScreen(),
                      ],
                    ),
                  ),
                ],
              );

              bodyArea = BlocProvider<SearchCubit>(
                create: (context) => SearchCubit(
                  allMatches: state.allMatches.cast<MatchModel>(),
                  allRecommendations: state.filteredRecommendations,
                ),
                child: content,
              );
            } else {
              bodyArea = Column(
                children: [
                  if (isDesktop)
                    DesktopHeader(
                      currentIndex: _currentIndex,
                      onTabChanged: (i) => setState(() => _currentIndex = i),
                    ),
                  Expanded(
                    child: IndexedStack(
                      index: _currentIndex,
                      children: [
                        HomeScreen(
                          onViewAllPredictions: () =>
                              setState(() => _currentIndex = 2),
                        ),
                        const BacktestDashboard(),
                        const TopPredictionsScreen(),
                        const AccountScreen(),
                      ],
                    ),
                  ),
                ],
              );
            }

            return Scaffold(
              extendBody: true,
              body: bodyArea,
              bottomNavigationBar:
                  isDesktop ? null : _buildFloatingNavBar(isDark),
            );
          },
        );
      },
    );
  }

  Widget _buildFloatingNavBar(bool isDark) {
    return Container(
      height: Responsive.sp(context, 48),
      margin: EdgeInsets.fromLTRB(
        Responsive.sp(context, 16),
        0,
        Responsive.sp(context, 16),
        Responsive.sp(context, 24), // Lifted off the bottom
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(Responsive.sp(context, 24)),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 15, sigmaY: 15),
          child: Container(
            decoration: BoxDecoration(
              color: isDark
                  ? const Color(0xFF162130).withValues(alpha: 0.85) // Deep navy
                  : Colors.white.withValues(alpha: 0.85),
              borderRadius: BorderRadius.circular(Responsive.sp(context, 24)),
              border: Border.all(
                color: isDark
                    ? Colors.white.withValues(alpha: 0.08)
                    : Colors.black.withValues(alpha: 0.05),
                width: 0.5,
              ),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.2),
                  blurRadius: 10,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _buildNavItem(0, Icons.chat_bubble_rounded, "HOME",
                    badge: "19"),
                _buildNavItem(1, Icons.science_rounded, "RULES"),
                _buildNavItem(2, Icons.emoji_events_rounded, "TOP"),
                _buildNavItem(3, Icons.person_rounded, "PROFILE"),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildNavItem(int index, IconData icon, String label,
      {String? badge}) {
    final isSelected = _currentIndex == index;
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return GestureDetector(
      onTap: () {
        setState(() => _currentIndex = index);
        HapticFeedback.lightImpact();
      },
      behavior: HitTestBehavior.opaque,
      child: Container(
        padding: EdgeInsets.symmetric(horizontal: Responsive.sp(context, 10)),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Stack(
              clipBehavior: Clip.none,
              children: [
                AnimatedContainer(
                  duration: const Duration(milliseconds: 300),
                  padding: EdgeInsets.symmetric(
                    horizontal: Responsive.sp(context, 14),
                    vertical: Responsive.sp(context, 4),
                  ),
                  decoration: BoxDecoration(
                    color: isSelected
                        ? AppColors.primary.withValues(alpha: 0.2)
                        : Colors.transparent,
                    borderRadius: BorderRadius.circular(20),
                    boxShadow: isSelected
                        ? [
                            BoxShadow(
                              color: AppColors.primary.withValues(alpha: 0.1),
                              blurRadius: 10,
                              spreadRadius: 2,
                            )
                          ]
                        : [],
                  ),
                  child: Icon(
                    icon,
                    size: Responsive.sp(context, 15),
                    color: isSelected
                        ? AppColors.primary
                        : (isDark ? Colors.white54 : Colors.black45),
                  ),
                ),
                if (badge != null)
                  Positioned(
                    top: -5,
                    right: 2,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 4, vertical: 1),
                      decoration: BoxDecoration(
                        color: const Color(0xFF3B82F6), // Blue badge
                        borderRadius: BorderRadius.circular(10),
                      ),
                      constraints: BoxConstraints(
                        minWidth: Responsive.sp(context, 10),
                      ),
                      child: Text(
                        badge,
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: Responsive.sp(context, 5.5),
                          fontWeight: FontWeight.bold,
                        ),
                        textAlign: TextAlign.center,
                      ),
                    ),
                  ),
              ],
            ),
            SizedBox(height: Responsive.sp(context, 2)),
            Text(
              label,
              style: TextStyle(
                fontSize: Responsive.sp(context, 5.5),
                fontWeight: isSelected ? FontWeight.w900 : FontWeight.w600,
                color: isSelected
                    ? AppColors.primary
                    : (isDark ? Colors.white38 : Colors.black38),
                letterSpacing: 0.2,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
