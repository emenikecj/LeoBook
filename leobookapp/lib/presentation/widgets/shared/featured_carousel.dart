// featured_carousel.dart: featured_carousel.dart: Widget/screen for App — Widgets.
// Part of LeoBook App — Widgets
//
// Classes: FeaturedCarousel

import 'package:flutter/material.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/core/constants/responsive_constants.dart';
import 'package:leobookapp/data/models/match_model.dart';
import 'package:leobookapp/data/models/recommendation_model.dart';
import 'recommendation_card.dart';

class FeaturedCarousel extends StatelessWidget {
  final List<MatchModel> matches;
  final List<RecommendationModel> recommendations;
  final List<MatchModel> allMatches;
  final VoidCallback? onViewAll;

  const FeaturedCarousel({
    super.key,
    required this.matches,
    required this.recommendations,
    required this.allMatches,
    this.onViewAll,
  });

  @override
  Widget build(BuildContext context) {
    if (recommendations.isEmpty) return const SizedBox.shrink();

    final isDesktop = Responsive.isDesktop(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: EdgeInsets.symmetric(
            horizontal: Responsive.sp(context, 10),
            vertical: Responsive.sp(context, 6),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  Icon(
                    Icons.auto_awesome,
                    color: AppColors.primary,
                    size: Responsive.sp(context, 14),
                  ),
                  SizedBox(width: Responsive.sp(context, 5)),
                  Text(
                    "TOP PREDICTIONS",
                    style: TextStyle(
                      fontSize: Responsive.sp(context, 10),
                      fontWeight: FontWeight.w900,
                      letterSpacing: 1.0,
                      color: Theme.of(context).brightness == Brightness.dark
                          ? Colors.white
                          : AppColors.textDark,
                    ),
                  ),
                ],
              ),
              GestureDetector(
                onTap: onViewAll,
                child: Text(
                  "VIEW ALL",
                  style: TextStyle(
                    color: AppColors.primary,
                    fontSize: Responsive.sp(context, 8),
                    fontWeight: FontWeight.w900,
                    letterSpacing: 0.8,
                  ),
                ),
              ),
            ],
          ),
        ),
        if (isDesktop)
          Padding(
            padding:
                EdgeInsets.symmetric(horizontal: Responsive.sp(context, 10)),
            child: LayoutBuilder(
              builder: (context, constraints) {
                const crossAxisCount = 3;
                final spacing = Responsive.sp(context, 14);
                final itemWidth =
                    (constraints.maxWidth - (spacing * (crossAxisCount - 1))) /
                        crossAxisCount;

                // Show only first 4 (or 8) if we want to keep it "featured"
                // But usually, on desktop, we can show a few more or the same as mobile
                final displayRecs = recommendations.take(8).toList();

                return Wrap(
                  spacing: spacing,
                  runSpacing: spacing,
                  children: displayRecs
                      .map(
                        (rec) => SizedBox(
                          width: itemWidth,
                          child: RecommendationCard(recommendation: rec),
                        ),
                      )
                      .toList(),
                );
              },
            ),
          )
        else
          Padding(
            padding:
                EdgeInsets.symmetric(horizontal: Responsive.sp(context, 10)),
            child: Column(
              children: recommendations
                  .take(5) // Show only a few on home screen mobile
                  .map((rec) => Padding(
                        padding:
                            EdgeInsets.only(bottom: Responsive.sp(context, 8)),
                        child: RecommendationCard(recommendation: rec),
                      ))
                  .toList(),
            ),
          ),
      ],
    );
  }
}
