// accuracy_report_card.dart: Data-driven accuracy report computed from predictions.
// Part of LeoBook App — Responsive Widgets
//
// Classes: AccuracyReportCard, _LeagueAccuracyGrid, _SectionHeader, _LeagueAccuracy

import 'package:flutter/material.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/responsive_constants.dart';
import '../../../data/models/match_model.dart';

class AccuracyReportCard extends StatelessWidget {
  final List<MatchModel> matches;

  const AccuracyReportCard({super.key, required this.matches});

  @override
  Widget build(BuildContext context) {
    final isDesktop = Responsive.isDesktop(context);

    // Compute accuracy from finished matches with predictions
    final finished = matches
        .where((m) =>
            m.isFinished && m.prediction != null && m.prediction!.isNotEmpty)
        .toList();

    final accurate = finished.where((m) => m.isPredictionAccurate).length;
    final totalAccuracy =
        finished.isNotEmpty ? (accurate / finished.length * 100).round() : 0;

    // Compute per-league accuracy (top 3 leagues by match count)
    final leagueStats = _computeLeagueAccuracy(finished);

    // Performance label
    String perfLabel = "AWAITING DATA";
    Color perfColor = AppColors.textGrey;
    IconData trendIcon = Icons.remove_rounded;

    if (finished.isNotEmpty) {
      if (totalAccuracy >= 80) {
        perfLabel = "HIGH PERFORMANCE";
        perfColor = AppColors.successGreen;
        trendIcon = Icons.trending_up_rounded;
      } else if (totalAccuracy >= 60) {
        perfLabel = "AVERAGE";
        perfColor = AppColors.warning;
        trendIcon = Icons.trending_flat_rounded;
      } else {
        perfLabel = "NEEDS IMPROVEMENT";
        perfColor = AppColors.liveRed;
        trendIcon = Icons.trending_down_rounded;
      }
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            _SectionHeader(
              title: "ACCURACY REPORT",
              icon: Icons.check_circle_rounded,
              color: AppColors.successGreen,
            ),
            Text(
              "${finished.length} MATCHES ANALYZED",
              style: TextStyle(
                fontSize: Responsive.sp(context, 7),
                fontWeight: FontWeight.w900,
                color: AppColors.textGrey,
                letterSpacing: 1.5,
              ),
            ),
          ],
        ),
        SizedBox(height: Responsive.sp(context, 10)),
        Container(
          padding: EdgeInsets.all(Responsive.sp(context, 12)),
          decoration: BoxDecoration(
            color: AppColors.desktopSearchFill.withValues(alpha: 0.5),
            borderRadius: BorderRadius.circular(Responsive.sp(context, 14)),
            border: Border.all(color: Colors.white.withValues(alpha: 0.05)),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (isDesktop)
                SizedBox(
                  height: Responsive.sp(context, 80),
                  child: Row(
                    children: [
                      _buildMainAccuracy(context, totalAccuracy, perfLabel,
                          perfColor, trendIcon),
                      const SizedBox(width: 32),
                      Container(width: 1, color: Colors.white10),
                      const SizedBox(width: 32),
                      Expanded(
                          child: _LeagueAccuracyGrid(leagues: leagueStats)),
                    ],
                  ),
                )
              else
                Column(
                  children: [
                    _buildMainAccuracy(context, totalAccuracy, perfLabel,
                        perfColor, trendIcon),
                    SizedBox(height: Responsive.sp(context, 12)),
                    _LeagueAccuracyGrid(leagues: leagueStats),
                  ],
                ),
            ],
          ),
        ),
      ],
    );
  }

  List<_LeagueAccData> _computeLeagueAccuracy(List<MatchModel> finished) {
    final Map<String, List<MatchModel>> byLeague = {};
    for (var m in finished) {
      final league = m.league ?? 'Unknown';
      // Extract short league name (after colon if present)
      String shortName = league;
      if (league.contains(':')) {
        shortName = league.split(':').last.trim();
      }
      byLeague.putIfAbsent(shortName, () => []).add(m);
    }

    // Sort by match count descending, take top 3
    final sorted = byLeague.entries.toList()
      ..sort((a, b) => b.value.length.compareTo(a.value.length));

    final colors = [
      AppColors.primary,
      AppColors.warning,
      AppColors.successGreen
    ];

    return sorted.take(3).toList().asMap().entries.map((entry) {
      final i = entry.key;
      final e = entry.value;
      final acc = e.value.where((m) => m.isPredictionAccurate).length;
      final pct = e.value.isNotEmpty ? acc / e.value.length : 0.0;
      // Truncate league name for display
      String label = e.key;
      if (label.length > 12) label = label.substring(0, 12);

      return _LeagueAccData(
        label: label.toUpperCase(),
        percentage: pct,
        color: colors[i % colors.length],
      );
    }).toList();
  }

  Widget _buildMainAccuracy(BuildContext context, int totalAccuracy,
      String perfLabel, Color perfColor, IconData trendIcon) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Text(
          "TOTAL ACCURACY",
          style: TextStyle(
            fontSize: Responsive.sp(context, 7),
            fontWeight: FontWeight.w900,
            color: AppColors.textGrey,
            letterSpacing: 1.5,
          ),
        ),
        Row(
          crossAxisAlignment: CrossAxisAlignment.baseline,
          textBaseline: TextBaseline.alphabetic,
          children: [
            Text(
              "$totalAccuracy",
              style: TextStyle(
                fontSize: Responsive.sp(context, 32),
                fontWeight: FontWeight.w900,
                color: Colors.white,
                fontStyle: FontStyle.italic,
                letterSpacing: -1,
              ),
            ),
            Text(
              "%",
              style: TextStyle(
                fontSize: Responsive.sp(context, 14),
                fontWeight: FontWeight.w700,
                color: perfColor,
              ),
            ),
            SizedBox(width: Responsive.sp(context, 4)),
            Icon(
              trendIcon,
              color: perfColor,
              size: Responsive.sp(context, 20),
            ),
          ],
        ),
        SizedBox(height: Responsive.sp(context, 4)),
        Container(
          padding: EdgeInsets.symmetric(
            horizontal: Responsive.sp(context, 6),
            vertical: Responsive.sp(context, 3),
          ),
          decoration: BoxDecoration(
            color: perfColor.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(Responsive.sp(context, 4)),
          ),
          child: Text(
            perfLabel,
            style: TextStyle(
              fontSize: Responsive.sp(context, 6),
              fontWeight: FontWeight.w900,
              color: perfColor,
              letterSpacing: 1,
            ),
          ),
        ),
      ],
    );
  }
}

class _LeagueAccData {
  final String label;
  final double percentage;
  final Color color;
  const _LeagueAccData(
      {required this.label, required this.percentage, required this.color});
}

class _LeagueAccuracyGrid extends StatelessWidget {
  final List<_LeagueAccData> leagues;
  const _LeagueAccuracyGrid({required this.leagues});

  @override
  Widget build(BuildContext context) {
    if (leagues.isEmpty) {
      return Center(
        child: Text(
          "NO LEAGUE DATA YET",
          style: TextStyle(
            fontSize: Responsive.sp(context, 7),
            color: AppColors.textGrey,
            fontWeight: FontWeight.w900,
          ),
        ),
      );
    }

    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: leagues
          .map((l) => Expanded(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  child: _LeagueAccuracy(
                    label: l.label,
                    percentage: l.percentage,
                    color: l.color,
                  ),
                ),
              ))
          .toList(),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final String title;
  final IconData icon;
  final Color color;

  const _SectionHeader({
    required this.title,
    required this.icon,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, color: color, size: Responsive.sp(context, 12)),
        SizedBox(width: Responsive.sp(context, 6)),
        Text(
          title,
          style: TextStyle(
            fontSize: Responsive.sp(context, 9),
            fontWeight: FontWeight.w900,
            letterSpacing: 1.5,
            color: Colors.white,
          ),
        ),
      ],
    );
  }
}

class _LeagueAccuracy extends StatelessWidget {
  final String label;
  final double percentage;
  final Color color;

  const _LeagueAccuracy({
    required this.label,
    required this.percentage,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.all(Responsive.sp(context, 8)),
      decoration: BoxDecoration(
        color: AppColors.desktopHeaderBg,
        borderRadius: BorderRadius.circular(Responsive.sp(context, 10)),
        border: Border.all(color: Colors.white.withValues(alpha: 0.05)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Flexible(
                child: Text(
                  label,
                  style: TextStyle(
                    fontSize: Responsive.sp(context, 6),
                    fontWeight: FontWeight.w900,
                    color: AppColors.textGrey,
                    letterSpacing: 1.0,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              Icon(Icons.sports_soccer_rounded,
                  color: color.withValues(alpha: 0.5),
                  size: Responsive.sp(context, 8)),
            ],
          ),
          SizedBox(height: Responsive.sp(context, 8)),
          Text(
            "${(percentage * 100).toInt()}%",
            style: TextStyle(
              fontSize: Responsive.sp(context, 16),
              fontWeight: FontWeight.w900,
              color: Colors.white,
              fontStyle: FontStyle.italic,
              letterSpacing: -0.5,
            ),
          ),
          SizedBox(height: Responsive.sp(context, 4)),
          Container(
            height: Responsive.sp(context, 2),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.05),
              borderRadius: BorderRadius.circular(10),
            ),
            child: FractionallySizedBox(
              alignment: Alignment.centerLeft,
              widthFactor: percentage.clamp(0.0, 1.0),
              child: Container(
                decoration: BoxDecoration(
                  color: color,
                  borderRadius: BorderRadius.circular(10),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
