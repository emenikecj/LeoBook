// accuracy_report_card.dart: accuracy_report_card.dart: Widget/screen for App — Responsive Widgets.
// Part of LeoBook App — Responsive Widgets
//
// Classes: AccuracyReportCard, _LeagueAccuracyGrid, _SectionHeader, _LeagueAccuracy

import 'package:flutter/material.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/responsive_constants.dart';

class AccuracyReportCard extends StatelessWidget {
  const AccuracyReportCard({super.key});

  @override
  Widget build(BuildContext context) {
    final isDesktop = Responsive.isDesktop(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            _SectionHeader(
              title: "YESTERDAY'S ACCURACY REPORT",
              icon: Icons.check_circle_rounded,
              color: AppColors.successGreen,
            ),
            Text(
              "24 MATCHES ANALYZED",
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
                      _buildMainAccuracy(context),
                      const SizedBox(width: 32),
                      Container(width: 1, color: Colors.white10),
                      const SizedBox(width: 32),
                      const Expanded(child: _LeagueAccuracyGrid()),
                    ],
                  ),
                )
              else
                Column(
                  children: [
                    _buildMainAccuracy(context),
                    SizedBox(height: Responsive.sp(context, 12)),
                    const _LeagueAccuracyGrid(),
                  ],
                ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildMainAccuracy(BuildContext context) {
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
              "88",
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
                color: AppColors.successGreen,
              ),
            ),
            SizedBox(width: Responsive.sp(context, 4)),
            Icon(
              Icons.trending_up_rounded,
              color: AppColors.successGreen,
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
            color: AppColors.successGreen.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(Responsive.sp(context, 4)),
          ),
          child: Text(
            "HIGH PERFORMANCE",
            style: TextStyle(
              fontSize: Responsive.sp(context, 6),
              fontWeight: FontWeight.w900,
              color: AppColors.successGreen,
              letterSpacing: 1,
            ),
          ),
        ),
      ],
    );
  }
}

class _LeagueAccuracyGrid extends StatelessWidget {
  const _LeagueAccuracyGrid();

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: const [
        Expanded(
          child: _LeagueAccuracy(
            label: "EPL",
            percentage: 0.92,
            color: AppColors.primary,
            icon: Icons.sports_soccer_rounded,
          ),
        ),
        SizedBox(width: 8),
        Expanded(
          child: _LeagueAccuracy(
            label: "NBA",
            percentage: 0.85,
            color: AppColors.warning,
            icon: Icons.sports_basketball_rounded,
          ),
        ),
        SizedBox(width: 8),
        Expanded(
          child: _LeagueAccuracy(
            label: "LIGA",
            percentage: 0.80,
            color: AppColors.successGreen,
            icon: Icons.sports_soccer_rounded,
          ),
        ),
      ],
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
  final IconData icon;

  const _LeagueAccuracy({
    required this.label,
    required this.percentage,
    required this.color,
    required this.icon,
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
              Icon(icon,
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
              widthFactor: percentage,
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
