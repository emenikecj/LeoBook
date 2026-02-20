// main_screen.dart: main_screen.dart: Widget/screen for App — Screens.
// Part of LeoBook App — Screens
//
// Classes: MainScreen, _MainScreenState

import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/core/theme/liquid_glass_theme.dart';
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
              bottomNavigationBar: isDesktop
                  ? null
                  : Container(
                      color: Colors.transparent,
                      margin: EdgeInsets.symmetric(
                        horizontal: Responsive.sp(context, 20),
                        vertical: Responsive.sp(context, 14),
                      ),
                      child: ClipRRect(
                        borderRadius:
                            BorderRadius.circular(Responsive.sp(context, 40)),
                        child: BackdropFilter(
                          filter: ImageFilter.blur(
                            sigmaX: LiquidGlassTheme.blurRadiusMedium,
                            sigmaY: LiquidGlassTheme.blurRadiusMedium,
                          ),
                          child: Container(
                            padding: EdgeInsets.symmetric(
                              horizontal: Responsive.sp(context, 12),
                              vertical: Responsive.sp(context, 4),
                            ),
                            decoration: BoxDecoration(
                              color: isDark
                                  ? AppColors.cardDark.withValues(alpha: 0.35)
                                  : Colors.white.withValues(alpha: 0.35),
                              borderRadius: BorderRadius.circular(
                                  Responsive.sp(context, 40)),
                              border: Border.all(
                                color: LiquidGlassTheme.glassBorder(
                                  Theme.of(context).brightness,
                                ),
                                width: 0.5,
                              ),
                            ),
                            child: BottomNavigationBar(
                              currentIndex: _currentIndex,
                              onTap: (index) {
                                setState(() => _currentIndex = index);
                                HapticFeedback.lightImpact();
                              },
                              backgroundColor: Colors.transparent,
                              elevation: 0,
                              type: BottomNavigationBarType.fixed,
                              selectedItemColor: AppColors.primary,
                              unselectedItemColor: Colors.white38,
                              showSelectedLabels: true,
                              showUnselectedLabels: true,
                              selectedFontSize: Responsive.sp(context, 7),
                              unselectedFontSize: Responsive.sp(context, 7),
                              selectedLabelStyle: TextStyle(
                                fontSize: Responsive.sp(context, 7),
                                fontWeight: FontWeight.w900,
                                letterSpacing: 0.5,
                              ),
                              unselectedLabelStyle: TextStyle(
                                fontSize: Responsive.sp(context, 7),
                                color: Colors
                                    .transparent, // Hidden but occupies space
                              ),
                              items: [
                                _buildNavItem(
                                  Icons.home_rounded,
                                  Icons.home_outlined,
                                  0,
                                  "HOME",
                                ),
                                _buildNavItem(
                                  Icons.science_rounded,
                                  Icons.science_outlined,
                                  1,
                                  "RULES",
                                ),
                                _buildNavItem(
                                  Icons.emoji_events_rounded,
                                  Icons.emoji_events_outlined,
                                  2,
                                  "TOP",
                                ),
                                _buildNavItem(
                                  Icons.person_rounded,
                                  Icons.person_outline_rounded,
                                  3,
                                  "PROFILE",
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
            );
          },
        );
      },
    );
  }

  BottomNavigationBarItem _buildNavItem(
    IconData activeIcon,
    IconData inactiveIcon,
    int index,
    String label,
  ) {
    final isSelected = _currentIndex == index;
    final iconSize = Responsive.sp(context, 16);
    return BottomNavigationBarItem(
      icon: Container(
        padding: EdgeInsets.all(Responsive.sp(context, 5)),
        decoration: const BoxDecoration(
          color: Colors.transparent,
          shape: BoxShape.circle,
        ),
        child: AnimatedScale(
          scale: isSelected ? 1.0 : 0.85,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOutCubic,
          child: Icon(inactiveIcon, size: iconSize),
        ),
      ),
      activeIcon: AnimatedScale(
        scale: 1.0,
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOutCubic,
        child: Container(
          padding: EdgeInsets.all(Responsive.sp(context, 5)),
          decoration: BoxDecoration(
            color: AppColors.primary.withValues(alpha: 0.12),
            shape: BoxShape.circle,
          ),
          child: Icon(activeIcon, size: iconSize),
        ),
      ),
      label: label,
    );
  }
}
