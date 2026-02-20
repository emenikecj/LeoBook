// recommendation_card.dart: recommendation_card.dart: Widget/screen for App — Widgets.
// Part of LeoBook App — Widgets
//
// Classes: RecommendationCard, _RecommendationCardState, _LivePulseTag, _LivePulseTagState

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/core/constants/responsive_constants.dart';
import 'package:leobookapp/data/models/recommendation_model.dart';
import 'package:leobookapp/data/repositories/data_repository.dart';
import '../../screens/team_screen.dart';
import '../../screens/league_screen.dart';
import 'package:leobookapp/core/widgets/glass_container.dart';

class RecommendationCard extends StatefulWidget {
  final RecommendationModel recommendation;

  const RecommendationCard({super.key, required this.recommendation});

  @override
  State<RecommendationCard> createState() => _RecommendationCardState();
}

class _RecommendationCardState extends State<RecommendationCard> {
  bool _isHovered = false;

  RecommendationModel get rec => widget.recommendation;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final isLive = rec.confidence.toLowerCase().contains('live') ||
        rec.league.toLowerCase().contains('live');
    final accentColor = isLive ? AppColors.liveRed : AppColors.primary;

    return MouseRegion(
      onEnter: (_) => setState(() => _isHovered = true),
      onExit: (_) => setState(() => _isHovered = false),
      child: AnimatedScale(
        scale: _isHovered ? 1.012 : 1.0,
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOutCubic,
        child: GlassContainer(
          margin: EdgeInsets.symmetric(
            horizontal: Responsive.sp(context, 4),
            vertical: Responsive.sp(context, 4),
          ),
          padding: EdgeInsets.all(Responsive.sp(context, 10)),
          borderRadius: Responsive.sp(context, 10),
          borderColor: _isHovered
              ? accentColor.withValues(alpha: 0.5)
              : (isLive
                  ? AppColors.liveRed.withValues(alpha: 0.3)
                  : AppColors.primary.withValues(alpha: 0.2)),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // ── League + Time Row ──
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Flexible(
                    child: GestureDetector(
                      onTap: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (context) => LeagueScreen(
                              leagueId: rec.league,
                              leagueName: rec.league,
                            ),
                          ),
                        );
                      },
                      child: Text(
                        rec.league.toUpperCase(),
                        maxLines: 1,
                        style: TextStyle(
                          color: AppColors.textGrey.withValues(alpha: 0.8),
                          fontSize: Responsive.sp(context, 7),
                          fontWeight: FontWeight.w900,
                          letterSpacing: 1.0,
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ),
                  SizedBox(width: Responsive.sp(context, 6)),
                  if (isLive)
                    _LivePulseTag()
                  else
                    Text(
                      "${rec.date} • ${rec.time}".toUpperCase(),
                      style: TextStyle(
                        color: AppColors.primary,
                        fontSize: Responsive.sp(context, 7),
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                ],
              ),

              SizedBox(height: Responsive.sp(context, 6)),

              // ── Teams Row ──
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  // Home Team
                  Expanded(
                      child: _buildTeamCol(
                          context, rec.homeTeam, rec.homeShort, isDark)),
                  // VS
                  Padding(
                    padding: EdgeInsets.symmetric(
                        horizontal: Responsive.sp(context, 6)),
                    child: Text(
                      "VS",
                      style: TextStyle(
                        fontSize: Responsive.sp(context, 9),
                        fontWeight: FontWeight.w900,
                        fontStyle: FontStyle.italic,
                        color: AppColors.textGrey,
                      ),
                    ),
                  ),
                  // Away Team
                  Expanded(
                      child: _buildTeamCol(
                          context, rec.awayTeam, rec.awayShort, isDark)),
                ],
              ),

              SizedBox(height: Responsive.sp(context, 6)),

              // ── Prediction Section (glass inner) ──
              Container(
                padding: EdgeInsets.all(Responsive.sp(context, 7)),
                decoration: BoxDecoration(
                  color: isLive
                      ? AppColors.liveRed.withValues(alpha: 0.08)
                      : (isDark
                          ? Colors.white.withValues(alpha: 0.05)
                          : Colors.black.withValues(alpha: 0.03)),
                  borderRadius:
                      BorderRadius.circular(Responsive.sp(context, 6)),
                  border: Border.all(
                    color: isLive
                        ? AppColors.liveRed.withValues(alpha: 0.15)
                        : (isDark
                            ? Colors.white.withValues(alpha: 0.06)
                            : Colors.black.withValues(alpha: 0.04)),
                    width: 0.5,
                  ),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    // Left: Prediction + Reliability
                    Flexible(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            isLive ? "IN-PLAY PREDICTION" : "LEO PREDICTION",
                            style: TextStyle(
                              fontSize: Responsive.sp(context, 6),
                              fontWeight: FontWeight.w900,
                              color: isLive
                                  ? AppColors.liveRed
                                  : AppColors.textGrey,
                              letterSpacing: 0.3,
                            ),
                          ),
                          SizedBox(height: Responsive.sp(context, 1)),
                          Text(
                            rec.prediction,
                            maxLines: 1,
                            style: TextStyle(
                              fontSize: Responsive.sp(context, 9),
                              fontWeight: FontWeight.w900,
                              color: AppColors.primary,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                          SizedBox(height: Responsive.sp(context, 2)),
                          Row(
                            children: [
                              Text(
                                "RELIABILITY: ${(rec.reliabilityScore * 10).toStringAsFixed(0)}%",
                                style: TextStyle(
                                  fontSize: Responsive.sp(context, 6),
                                  fontWeight: FontWeight.bold,
                                  color:
                                      AppColors.success.withValues(alpha: 0.7),
                                ),
                              ),
                              SizedBox(width: Responsive.sp(context, 6)),
                              Text(
                                "ACC: ${rec.overallAcc}",
                                style: TextStyle(
                                  fontSize: Responsive.sp(context, 6),
                                  fontWeight: FontWeight.bold,
                                  color:
                                      AppColors.textGrey.withValues(alpha: 0.6),
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                    SizedBox(width: Responsive.sp(context, 4)),
                    // Right: Odds pill
                    if (rec.marketOdds > 0)
                      Container(
                        padding: EdgeInsets.symmetric(
                          horizontal: Responsive.sp(context, 8),
                          vertical: Responsive.sp(context, 3),
                        ),
                        decoration: BoxDecoration(
                          color: AppColors.primary.withValues(alpha: 0.12),
                          borderRadius:
                              BorderRadius.circular(Responsive.sp(context, 6)),
                          border: Border.all(
                            color: AppColors.primary.withValues(alpha: 0.25),
                            width: 0.5,
                          ),
                        ),
                        child: Text(
                          rec.marketOdds.toStringAsFixed(2),
                          style: TextStyle(
                            fontSize: Responsive.sp(context, 10),
                            fontWeight: FontWeight.w900,
                            color: AppColors.primary,
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTeamCol(
      BuildContext context, String teamName, String shortName, bool isDark) {
    final logoSize = Responsive.sp(context, 28);
    return GestureDetector(
      onTap: () {
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (context) => TeamScreen(
              teamName: teamName,
              repository: context.read<DataRepository>(),
            ),
          ),
        );
      },
      child: Column(
        children: [
          Container(
            width: logoSize,
            height: logoSize,
            decoration: BoxDecoration(
              color: isDark
                  ? Colors.white.withValues(alpha: 0.05)
                  : Colors.black.withValues(alpha: 0.03),
              shape: BoxShape.circle,
              border: Border.all(
                color: isDark
                    ? Colors.white.withValues(alpha: 0.06)
                    : Colors.black.withValues(alpha: 0.04),
                width: 0.5,
              ),
            ),
            child: Center(
              child: Text(
                shortName,
                style: TextStyle(
                  fontWeight: FontWeight.w900,
                  fontSize: Responsive.sp(context, 10),
                  color: AppColors.textGrey.withValues(alpha: 0.5),
                ),
              ),
            ),
          ),
          SizedBox(height: Responsive.sp(context, 4)),
          Text(
            teamName,
            textAlign: TextAlign.center,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              fontSize: Responsive.sp(context, 8),
              fontWeight: FontWeight.w800,
              color: isDark ? Colors.white : AppColors.textDark,
            ),
          ),
        ],
      ),
    );
  }
}

class _LivePulseTag extends StatefulWidget {
  @override
  State<_LivePulseTag> createState() => _LivePulseTagState();
}

class _LivePulseTagState extends State<_LivePulseTag>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _animation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(seconds: 2),
      vsync: this,
    )..repeat();
    _animation = Tween<double>(begin: 1.0, end: 0.4).animate(_controller);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _animation,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: Responsive.sp(context, 4),
            height: Responsive.sp(context, 4),
            decoration: const BoxDecoration(
              color: AppColors.liveRed,
              shape: BoxShape.circle,
            ),
          ),
          SizedBox(width: Responsive.sp(context, 4)),
          Text(
            "LIVE NOW",
            style: TextStyle(
              color: AppColors.liveRed,
              fontSize: Responsive.sp(context, 7),
              fontWeight: FontWeight.w900,
            ),
          ),
        ],
      ),
    );
  }
}
