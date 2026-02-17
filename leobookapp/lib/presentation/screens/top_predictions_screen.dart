import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/data/models/recommendation_model.dart';
import 'package:leobookapp/data/models/match_model.dart';
import 'package:leobookapp/logic/cubit/home_cubit.dart';
import '../widgets/recommendation_card.dart';
import '../screens/match_details_screen.dart';
// We'll reuse the DateItem logic if possible, or just re-implement cleanly

class TopPredictionsScreen extends StatelessWidget {
  final bool isSidebarExpanded;
  const TopPredictionsScreen({super.key, this.isSidebarExpanded = true});

  void _navigateToMatch(
    BuildContext context,
    RecommendationModel rec,
    List<MatchModel> allMatches,
  ) {
    MatchModel? match;
    try {
      match = allMatches.firstWhere(
        (m) => m.fixtureId == rec.fixtureId && rec.fixtureId.isNotEmpty,
      );
    } catch (_) {
      try {
        match = allMatches.firstWhere(
          (m) =>
              rec.match.toLowerCase().contains(m.homeTeam.toLowerCase()) &&
              rec.match.toLowerCase().contains(m.awayTeam.toLowerCase()),
        );
      } catch (_) {}
    }

    if (match != null) {
      Navigator.push(
        context,
        MaterialPageRoute(builder: (_) => MatchDetailsScreen(match: match!)),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Match details not found in schedule.")),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDesktop = MediaQuery.of(context).size.width > 1024;

    return Scaffold(
      backgroundColor: AppColors.backgroundDark,
      appBar: isDesktop
          ? null
          : AppBar(
              backgroundColor: AppColors.backgroundDark.withValues(alpha: 0.8),
              elevation: 0,
              title: const Text(
                "Top Predictions",
                style: TextStyle(
                  fontWeight: FontWeight.w900,
                  color: Colors.white,
                  fontSize: 18,
                ),
              ),
              bottom: PreferredSize(
                preferredSize: const Size.fromHeight(80),
                child: _buildDateSelector(
                  context,
                  BlocProvider.of<HomeCubit>(context).state,
                ),
              ),
            ),
      body: BlocBuilder<HomeCubit, HomeState>(
        builder: (context, state) {
          if (state is! HomeLoaded) {
            return const Center(child: CircularProgressIndicator());
          }

          return CustomScrollView(
            slivers: [
              if (isDesktop)
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.all(32.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            IconButton(
                              onPressed: () => Navigator.pop(context),
                              icon: const Icon(Icons.arrow_back,
                                  color: Colors.white70),
                              padding: EdgeInsets.zero,
                              constraints: const BoxConstraints(),
                            ),
                            const SizedBox(width: 16),
                            const Text(
                              "TOP PREDICTIONS",
                              style: TextStyle(
                                fontSize: 24,
                                fontWeight: FontWeight.w900,
                                color: Colors.white,
                                letterSpacing: -1,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        const Text(
                          "Expert-curated match analyses with ultra-high accuracy targets.",
                          style: TextStyle(
                            fontSize: 14,
                            color: AppColors.textGrey,
                          ),
                        ),
                        const SizedBox(height: 32),
                        _buildDateSelector(context, state),
                      ],
                    ),
                  ),
                ),
              // Recommendations List/Grid
              state.filteredRecommendations.isEmpty
                  ? const SliverFillRemaining(
                      child: Center(
                        child: Text(
                          "No top predictions available.",
                          style: TextStyle(color: Colors.white54),
                        ),
                      ),
                    )
                  : SliverPadding(
                      padding: EdgeInsets.symmetric(
                        vertical: 16,
                        horizontal: isDesktop ? 32 : 0,
                      ),
                      sliver: isDesktop
                          ? SliverGrid(
                              gridDelegate:
                                  SliverGridDelegateWithFixedCrossAxisCount(
                                crossAxisCount: isSidebarExpanded ? 2 : 3,
                                crossAxisSpacing: 24,
                                mainAxisSpacing: 24,
                                childAspectRatio: 1.4,
                              ),
                              delegate: SliverChildBuilderDelegate(
                                (context, index) {
                                  final rec =
                                      state.filteredRecommendations[index];
                                  return GestureDetector(
                                    onTap: () => _navigateToMatch(
                                      context,
                                      rec,
                                      state.allMatches,
                                    ),
                                    child: RecommendationCard(
                                      recommendation: rec,
                                    ),
                                  );
                                },
                                childCount:
                                    state.filteredRecommendations.length,
                              ),
                            )
                          : SliverList(
                              delegate: SliverChildBuilderDelegate(
                                (context, index) {
                                  final rec =
                                      state.filteredRecommendations[index];
                                  return GestureDetector(
                                    onTap: () => _navigateToMatch(
                                      context,
                                      rec,
                                      state.allMatches,
                                    ),
                                    child: RecommendationCard(
                                      recommendation: rec,
                                    ),
                                  );
                                },
                                childCount:
                                    state.filteredRecommendations.length,
                              ),
                            ),
                    ),
            ],
          );
        },
      ),
    );
  }

  Widget _buildDateSelector(BuildContext context, HomeState state) {
    if (state is! HomeLoaded) return const SizedBox.shrink();
    return Container(
      padding: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        border: Border(
          bottom: BorderSide(color: Colors.white.withValues(alpha: 0.05)),
        ),
      ),
      child: SizedBox(
        height: 70,
        child: ListView.builder(
          scrollDirection: Axis.horizontal,
          itemCount: 7,
          padding: const EdgeInsets.symmetric(horizontal: 12),
          itemBuilder: (context, index) {
            final now = DateTime.now();
            final dayOffset = index - 3;
            final date = DateTime(
              now.year,
              now.month,
              now.day,
            ).add(Duration(days: dayOffset));

            final isSelected = date.year == state.selectedDate.year &&
                date.month == state.selectedDate.month &&
                date.day == state.selectedDate.day;

            return _buildDateItem(context, date, isSelected);
          },
        ),
      ),
    );
  }

  Widget _buildDateItem(BuildContext context, DateTime date, bool isSelected) {
    final now = DateTime.now();
    final isToday =
        date.year == now.year && date.month == now.month && date.day == now.day;
    final dayName =
        isToday ? "TODAY" : javaDateFormat('EEE', date).toUpperCase();
    final dayNum = javaDateFormat('d MMM', date).toUpperCase();

    return GestureDetector(
      onTap: () => context.read<HomeCubit>().updateDate(date),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOutCubic,
        width: 75,
        margin: const EdgeInsets.symmetric(horizontal: 4, vertical: 6),
        decoration: BoxDecoration(
          color: isSelected
              ? AppColors.primary.withValues(alpha: 0.12)
              : Colors.white.withValues(alpha: 0.04),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: isSelected
                ? AppColors.primary.withValues(alpha: 0.25)
                : Colors.white.withValues(alpha: 0.06),
          ),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              dayName,
              style: TextStyle(
                fontSize: 9,
                fontWeight: FontWeight.w900,
                color: isSelected ? AppColors.primary : Colors.white38,
                letterSpacing: 0.5,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              dayNum,
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.bold,
                color: isSelected ? AppColors.primary : Colors.white70,
              ),
            ),
          ],
        ),
      ),
    );
  }

  // Simple date formatter helper since intl's DateFormat might need initialization or be verbose here
  String javaDateFormat(String pattern, DateTime date) {
    final months = [
      "JAN",
      "FEB",
      "MAR",
      "APR",
      "MAY",
      "JUN",
      "JUL",
      "AUG",
      "SEP",
      "OCT",
      "NOV",
      "DEC",
    ];
    final days = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"];

    if (pattern == 'EEE') return days[date.weekday - 1];
    if (pattern == 'd MMM') return "${date.day} ${months[date.month - 1]}";
    return "";
  }
}
