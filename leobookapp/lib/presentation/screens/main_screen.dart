import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/presentation/screens/home_screen.dart';
import 'package:leobookapp/presentation/screens/account_screen.dart';
import 'package:leobookapp/presentation/screens/rule_engine/backtest_dashboard.dart';
import 'package:leobookapp/presentation/screens/top_predictions_screen.dart';
import 'package:leobookapp/presentation/widgets/responsive/navigation_sidebar.dart';
import 'package:leobookapp/presentation/widgets/responsive/desktop_header.dart';
import 'package:leobookapp/logic/cubit/search_cubit.dart';
import 'package:leobookapp/logic/cubit/home_cubit.dart';
import 'package:leobookapp/data/models/match_model.dart';

import '../widgets/responsive/global_stats_footer.dart';

class MainScreen extends StatefulWidget {
  const MainScreen({super.key});

  @override
  State<MainScreen> createState() => _MainScreenState();
}

class _MainScreenState extends State<MainScreen> {
  int _currentIndex = 0;
  bool _isSidebarExpanded = true;

  final List<Widget> _screens = [
    const HomeScreen(),
    const BacktestDashboard(),
    const TopPredictionsScreen(),
    const AccountScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return LayoutBuilder(
      builder: (context, constraints) {
        final isDesktop = constraints.maxWidth > 1024;

        if (isDesktop) {
          return Scaffold(
            body: Row(
              children: [
                NavigationSideBar(
                  currentIndex: _currentIndex,
                  isExpanded: _isSidebarExpanded,
                  onToggle: () =>
                      setState(() => _isSidebarExpanded = !_isSidebarExpanded),
                  onIndexChanged: (index) {
                    setState(() => _currentIndex = index);
                    HapticFeedback.lightImpact();
                  },
                ),
                Expanded(
                  child: BlocBuilder<HomeCubit, HomeState>(
                    builder: (context, state) {
                      if (state is HomeLoaded) {
                        return BlocProvider<SearchCubit>(
                          create: (context) => SearchCubit(
                            allMatches: state.allMatches.cast<MatchModel>(),
                            allRecommendations: state.filteredRecommendations,
                          ),
                          child: Column(
                            children: [
                              const DesktopHeader(),
                              Expanded(
                                child: IndexedStack(
                                  index: _currentIndex,
                                  children: [
                                    HomeScreen(
                                        isSidebarExpanded: _isSidebarExpanded),
                                    const BacktestDashboard(),
                                    const TopPredictionsScreen(),
                                    const AccountScreen(),
                                  ],
                                ),
                              ),
                              const GlobalStatsFooter(),
                            ],
                          ),
                        );
                      }
                      return Column(
                        children: [
                          const DesktopHeader(),
                          Expanded(
                            child: IndexedStack(
                              index: _currentIndex,
                              children: [
                                HomeScreen(
                                    isSidebarExpanded: _isSidebarExpanded),
                                const BacktestDashboard(),
                                const TopPredictionsScreen(),
                                const AccountScreen(),
                              ],
                            ),
                          ),
                          const GlobalStatsFooter(),
                        ],
                      );
                    },
                  ),
                ),
              ],
            ),
          );
        }

        return BlocBuilder<HomeCubit, HomeState>(
          builder: (context, state) {
            Widget scaffoldBody =
                IndexedStack(index: _currentIndex, children: _screens);

            if (state is HomeLoaded) {
              scaffoldBody = BlocProvider<SearchCubit>(
                create: (context) => SearchCubit(
                  allMatches: state.allMatches.cast<MatchModel>(),
                  allRecommendations: state.filteredRecommendations,
                ),
                child: scaffoldBody,
              );
            }

            return Scaffold(
              extendBody: false,
              body: scaffoldBody,
              bottomNavigationBar: Container(
                color: Colors.transparent,
                margin: const EdgeInsets.fromLTRB(58, 0, 58, 40),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(40),
                  child: BackdropFilter(
                    filter: ImageFilter.blur(sigmaX: 30, sigmaY: 30),
                    child: Container(
                      decoration: BoxDecoration(
                        color: isDark
                            ? AppColors.cardDark.withValues(alpha: 0.95)
                            : Colors.white.withValues(alpha: 0.95),
                        borderRadius: BorderRadius.circular(40),
                        border: Border.all(
                          color: isDark
                              ? Colors.white.withValues(alpha: 0.1)
                              : Colors.black.withValues(alpha: 0.05),
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
                        unselectedItemColor:
                            isDark ? Colors.white38 : AppColors.textGrey,
                        showSelectedLabels: true,
                        showUnselectedLabels: false,
                        selectedLabelStyle: const TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w900,
                          letterSpacing: 0.5,
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
    return BottomNavigationBarItem(
      icon: AnimatedScale(
        scale: isSelected ? 1.0 : 0.85,
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOutCubic,
        child: Icon(inactiveIcon, size: 22),
      ),
      activeIcon: AnimatedScale(
        scale: 1.0,
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOutCubic,
        child: Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: AppColors.primary.withValues(alpha: 0.12),
            shape: BoxShape.circle,
          ),
          child: Icon(activeIcon, size: 22),
        ),
      ),
      label: label,
    );
  }
}
