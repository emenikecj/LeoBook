// global_stats_footer.dart: global_stats_footer.dart: Widget/screen for App — Responsive Widgets.
// Part of LeoBook App — Responsive Widgets
//
// Classes: GlobalStatsFooter

import 'package:flutter/material.dart';
import '../../../core/constants/app_colors.dart';

class GlobalStatsFooter extends StatelessWidget {
  const GlobalStatsFooter({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 50,
      padding: const EdgeInsets.symmetric(horizontal: 32),
      decoration: const BoxDecoration(
        color: AppColors.desktopSidebarBg,
        border: Border(top: BorderSide(color: Colors.white10)),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          _buildStat(Icons.circle, "GLOBAL SUCCESS RATE: 84.5%", Colors.green),
          _buildStat(
            Icons.person_outline_rounded,
            "TOP PREDICTOR: @LEO_MASTER",
            AppColors.primary,
          ),
          _buildStat(
            Icons.trending_up_rounded,
            "TOTAL VOLUME TODAY: \$2.4M",
            Colors.orange,
          ),
        ],
      ),
    );
  }

  Widget _buildStat(IconData icon, String label, Color color) {
    return Row(
      children: [
        Icon(icon, color: color, size: 12),
        const SizedBox(width: 8),
        Text(
          label,
          style: const TextStyle(
            fontSize: 10,
            fontWeight: FontWeight.w900,
            color: AppColors.textGrey,
            letterSpacing: 1,
          ),
        ),
      ],
    );
  }
}
