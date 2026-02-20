// top_predictions_screen.dart: top_predictions_screen.dart: Widget/screen for App — Screens.
// Part of LeoBook App — Screens
//
// Classes: TopPredictionsScreen

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/core/constants/responsive_constants.dart';
import 'package:leobookapp/data/models/recommendation_model.dart';
import 'package:leobookapp/data/models/match_model.dart';
import 'package:leobookapp/logic/cubit/home_cubit.dart';
import '../widgets/shared/recommendation_card.dart';
import 'match_details_screen.dart';

/// Unified Top Predictions screen — lives inside MainScreen's IndexedStack.
/// No own Scaffold/AppBar. Shows recommendations for SCHEDULED matches,
/// sorted by time (latest first).
class TopPredictionsScreen extends StatelessWidget {
  const TopPredictionsScreen({super.key});

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
    return BlocBuilder<HomeCubit, HomeState>(
      builder: (context, state) {
        if (state is! HomeLoaded) {
          return const Center(child: CircularProgressIndicator());
        }

        // Filter to all top recommendations (sorted by time)
        // Usually these are scheduled/upcoming matches
        final recs = List<RecommendationModel>.from(state.allRecommendations);

        // Optional: Filter for upcoming only if desirable,
        // but often 'Top Predictions' includes the most relevant ones.
        // We sort by time (latest first as requested before, but if they are predictions
        // we might want earliest first? Actually the user previously said 'latest first').
        recs.sort((a, b) => b.time.compareTo(a.time));

        return Column(
          children: [
            // ── Header Row ──
            Padding(
              padding: EdgeInsets.fromLTRB(
                Responsive.sp(context, 14),
                Responsive.sp(context, 14),
                Responsive.sp(context, 14),
                Responsive.sp(context, 8),
              ),
              child: Row(
                children: [
                  Icon(
                    Icons.auto_awesome,
                    color: AppColors.primary,
                    size: Responsive.sp(context, 16),
                  ),
                  SizedBox(width: Responsive.sp(context, 6)),
                  Expanded(
                    child: Text(
                      "TOP PREDICTIONS",
                      style: TextStyle(
                        fontSize: Responsive.sp(context, 13),
                        fontWeight: FontWeight.w900,
                        letterSpacing: 1.5,
                        color: Colors.white,
                      ),
                    ),
                  ),
                  // Filter icon (placeholder)
                  Container(
                    padding: EdgeInsets.all(Responsive.sp(context, 6)),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.05),
                      borderRadius:
                          BorderRadius.circular(Responsive.sp(context, 8)),
                    ),
                    child: Icon(
                      Icons.filter_list_rounded,
                      color: Colors.white54,
                      size: Responsive.sp(context, 14),
                    ),
                  ),
                ],
              ),
            ),

            // ── Count ──
            Padding(
              padding: EdgeInsets.symmetric(
                horizontal: Responsive.sp(context, 14),
                vertical: Responsive.sp(context, 6),
              ),
              child: Row(
                children: [
                  Text(
                    "${recs.length} PREDICTION${recs.length == 1 ? '' : 'S'}",
                    style: TextStyle(
                      fontSize: Responsive.sp(context, 8),
                      fontWeight: FontWeight.w900,
                      color: AppColors.textGrey,
                      letterSpacing: 1.0,
                    ),
                  ),
                  const Spacer(),
                  Text(
                    "LATEST FIRST",
                    style: TextStyle(
                      fontSize: Responsive.sp(context, 7),
                      fontWeight: FontWeight.w700,
                      color: AppColors.primary.withValues(alpha: 0.7),
                      letterSpacing: 0.5,
                    ),
                  ),
                ],
              ),
            ),

            // ── Recommendations List ──
            Expanded(
              child: recs.isEmpty
                  ? Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(
                            Icons.emoji_events_outlined,
                            size: Responsive.sp(context, 36),
                            color: Colors.white12,
                          ),
                          SizedBox(height: Responsive.sp(context, 10)),
                          Text(
                            "No predictions available",
                            style: TextStyle(
                              fontSize: Responsive.sp(context, 11),
                              fontWeight: FontWeight.w700,
                              color: Colors.white24,
                            ),
                          ),
                          SizedBox(height: Responsive.sp(context, 4)),
                          Text(
                            "Check back later for new picks",
                            style: TextStyle(
                              fontSize: Responsive.sp(context, 8),
                              color: Colors.white12,
                            ),
                          ),
                        ],
                      ),
                    )
                  : Responsive.isDesktop(context)
                      ? SingleChildScrollView(
                          padding: EdgeInsets.fromLTRB(
                            Responsive.sp(context, 14),
                            0,
                            Responsive.sp(context, 14),
                            Responsive.sp(context, 80),
                          ),
                          child: LayoutBuilder(
                            builder: (context, constraints) {
                              const crossAxisCount = 4;
                              final spacing = Responsive.sp(context, 14);
                              final itemWidth = (constraints.maxWidth -
                                      (spacing * (crossAxisCount - 1))) /
                                  crossAxisCount;

                              return Wrap(
                                spacing: spacing,
                                runSpacing: spacing,
                                children: recs
                                    .map(
                                      (rec) => SizedBox(
                                        width: itemWidth,
                                        child: GestureDetector(
                                          onTap: () => _navigateToMatch(
                                            context,
                                            rec,
                                            state.allMatches,
                                          ),
                                          child: RecommendationCard(
                                              recommendation: rec),
                                        ),
                                      ),
                                    )
                                    .toList(),
                              );
                            },
                          ),
                        )
                      : ListView.builder(
                          padding: EdgeInsets.only(
                            bottom: Responsive.sp(context, 80),
                          ),
                          itemCount: recs.length,
                          itemBuilder: (context, index) {
                            final rec = recs[index];
                            return GestureDetector(
                              onTap: () => _navigateToMatch(
                                context,
                                rec,
                                state.allMatches,
                              ),
                              child: RecommendationCard(recommendation: rec),
                            );
                          },
                        ),
            ),
          ],
        );
      },
    );
  }
}
