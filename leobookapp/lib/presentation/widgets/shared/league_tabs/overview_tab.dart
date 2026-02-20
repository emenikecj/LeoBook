// overview_tab.dart: overview_tab.dart: Widget/screen for App — League Tab Widgets.
// Part of LeoBook App — League Tab Widgets
//
// Classes: LeagueOverviewTab, _LeagueOverviewTabState

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/data/models/match_model.dart';
import 'package:leobookapp/data/models/standing_model.dart';
import 'package:leobookapp/data/repositories/data_repository.dart';

class LeagueOverviewTab extends StatefulWidget {
  final String leagueName;
  const LeagueOverviewTab({super.key, required this.leagueName});

  @override
  State<LeagueOverviewTab> createState() => _LeagueOverviewTabState();
}

class _LeagueOverviewTabState extends State<LeagueOverviewTab> {
  bool _isLoading = true;
  List<StandingModel> _standings = [];
  List<MatchModel> _featuredMatches = [];

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    final repo = context.read<DataRepository>();
    final standings = await repo.getStandings(widget.leagueName);

    // Standard Sports Sorting: Points > GD > GF > Team Name
    standings.sort((a, b) {
      // 1. Points (Descending)
      if (b.points != a.points) return b.points.compareTo(a.points);

      // 2. Goal Difference (Descending)
      if (b.goalDiff != a.goalDiff) return b.goalDiff.compareTo(a.goalDiff);

      // 3. Goals For (Descending)
      if (b.goalsFor != a.goalsFor) return b.goalsFor.compareTo(a.goalsFor);

      // 4. Team Name (Ascending)
      return a.teamName.compareTo(b.teamName);
    });

    // For featured matches in this league, we'll fetch predictions for today
    final allPredictions = await repo.fetchMatches(date: DateTime.now());
    final leaguePredictions = allPredictions
        .where((m) => m.league == widget.leagueName && m.isFeatured)
        .toList();

    if (mounted) {
      setState(() {
        _standings = standings;
        _featuredMatches = leaguePredictions;
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildSectionHeader(context, "LEAGUE TABLE", Icons.table_chart),
          const SizedBox(height: 12),
          _buildLeagueTable(context, isDark),
          const SizedBox(height: 24),
          if (_featuredMatches.isNotEmpty) ...[
            _buildSectionHeader(context, "TOP PREDICTIONS", Icons.psychology),
            const SizedBox(height: 12),
            _buildPredictionsCarousel(context, isDark),
            const SizedBox(height: 24),
          ],
          _buildSectionHeader(context, "LEAGUE TRENDS", Icons.query_stats),
          const SizedBox(height: 12),
          _buildTrendsSection(context, isDark),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(
    BuildContext context,
    String title,
    IconData icon,
  ) {
    return Row(
      children: [
        Icon(icon, size: 16, color: AppColors.primary),
        const SizedBox(width: 8),
        Text(
          title,
          style: GoogleFonts.lexend(
            fontSize: 12,
            fontWeight: FontWeight.w800,
            color: AppColors.primary,
            letterSpacing: 1.2,
          ),
        ),
        const Spacer(),
        Icon(Icons.chevron_right, size: 16, color: AppColors.textGrey),
      ],
    );
  }

  Widget _buildLeagueTable(BuildContext context, bool isDark) {
    if (_standings.isEmpty) {
      return Container(
        height: 100,
        alignment: Alignment.center,
        child: Text(
          "No standings data available",
          style: TextStyle(color: AppColors.textGrey, fontSize: 12),
        ),
      );
    }

    return Container(
      decoration: BoxDecoration(
        color: isDark ? AppColors.cardDark : Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isDark
              ? Colors.white.withValues(alpha: 0.05)
              : Colors.black.withValues(alpha: 0.05),
        ),
      ),
      child: Column(
        children: [
          _buildTableHeader(isDark),
          ..._standings.asMap().entries.map((entry) {
            final index = entry.key;
            final s = entry.value;
            final rank = index + 1;
            return _buildTableRow(
              rank,
              s.teamName.substring(0, 3).toUpperCase(),
              s.teamName,
              s.played,
              s.wins,
              s.draws,
              s.losses,
              s.goalsFor - s.goalsAgainst,
              s.points,
              isDark,
              rank == 1,
            );
          }),
        ],
      ),
    );
  }

  Widget _buildTableHeader(bool isDark) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
      child: Row(
        children: [
          SizedBox(
            width: 24,
            child: Text(
              "#",
              style: GoogleFonts.lexend(
                fontSize: 10,
                fontWeight: FontWeight.bold,
                color: AppColors.textGrey,
              ),
              textAlign: TextAlign.center,
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            flex: 3,
            child: Text(
              "TEAM",
              style: GoogleFonts.lexend(
                fontSize: 10,
                fontWeight: FontWeight.bold,
                color: AppColors.textGrey,
              ),
            ),
          ),
          _buildHeaderCell("P"),
          _buildHeaderCell("W"),
          _buildHeaderCell("D"),
          _buildHeaderCell("L"),
          _buildHeaderCell("GD"),
          _buildHeaderCell("PTS", flex: 0, width: 35),
        ],
      ),
    );
  }

  Widget _buildHeaderCell(String label, {int flex = 1, double? width}) {
    return SizedBox(
      width: width ?? 25,
      child: Text(
        label,
        style: GoogleFonts.lexend(
          fontSize: 10,
          fontWeight: FontWeight.bold,
          color: AppColors.textGrey,
        ),
        textAlign: TextAlign.center,
      ),
    );
  }

  Widget _buildTableRow(
    int pos,
    String code,
    String name,
    int played,
    int wins,
    int draws,
    int losses,
    int gd,
    int pts,
    bool isDark,
    bool isFirst,
  ) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        border: Border(
          top: BorderSide(
            color: isDark
                ? Colors.white.withValues(alpha: 0.05)
                : Colors.black.withValues(alpha: 0.05),
          ),
        ),
      ),
      child: Row(
        children: [
          SizedBox(
            width: 24,
            child: Text(
              pos.toString(),
              style: GoogleFonts.lexend(
                fontSize: 12,
                fontWeight: FontWeight.w800,
                color: isFirst ? AppColors.primary : AppColors.textGrey,
              ),
              textAlign: TextAlign.center,
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            flex: 3,
            child: Text(
              name,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: GoogleFonts.lexend(
                fontSize: 12,
                fontWeight: FontWeight.w700,
                color: isDark ? Colors.white : AppColors.textDark,
              ),
            ),
          ),
          _buildDataCell(played.toString()),
          _buildDataCell(wins.toString()),
          _buildDataCell(draws.toString()),
          _buildDataCell(losses.toString()),
          _buildDataCell(gd.toString()),
          _buildDataCell(
            pts.toString(),
            width: 35,
            style: GoogleFonts.lexend(
              fontSize: 13,
              fontWeight: FontWeight.w900,
              color: isDark ? Colors.white : AppColors.textDark,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDataCell(String value, {double? width, TextStyle? style}) {
    return SizedBox(
      width: width ?? 25,
      child: Text(
        value,
        style:
            style ??
            GoogleFonts.lexend(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: AppColors.textGrey,
            ),
        textAlign: TextAlign.center,
      ),
    );
  }

  Widget _buildPredictionsCarousel(BuildContext context, bool isDark) {
    return SizedBox(
      height: 160,
      child: ListView(
        scrollDirection: Axis.horizontal,
        children: [
          _buildPredictionCard(
            context,
            "ARS",
            "CHE",
            "Arsenal",
            "Chelsea",
            "Home Win",
            "1.75",
            AppColors.primary,
            isDark,
          ),
          const SizedBox(width: 12),
          _buildPredictionCard(
            context,
            "MCI",
            "LIV",
            "Man City",
            "Liverpool",
            "Over 3.5 Goals",
            "2.40",
            AppColors.accentYellow,
            isDark,
          ),
        ],
      ),
    );
  }

  Widget _buildPredictionCard(
    BuildContext context,
    String homeCode,
    String awayCode,
    String homeName,
    String awayName,
    String prediction,
    String odds,
    Color color,
    bool isDark,
  ) {
    return Container(
      width: 260,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isDark ? AppColors.cardDark : Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isDark
              ? Colors.white.withValues(alpha: 0.05)
              : Colors.black.withValues(alpha: 0.05),
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Stack(
        children: [
          Positioned(
            left: 0,
            top: 0,
            bottom: 0,
            width: 4,
            child: Container(
              decoration: BoxDecoration(
                color: color,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.only(left: 12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    _buildTeamColumn(homeCode, homeName, isDark),
                    Text(
                      "VS",
                      style: GoogleFonts.lexend(
                        fontSize: 10,
                        fontWeight: FontWeight.w900,
                        fontStyle: FontStyle.italic,
                        color: AppColors.textGrey,
                      ),
                    ),
                    _buildTeamColumn(awayCode, awayName, isDark),
                  ],
                ),
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: color.withValues(alpha: 0.1)),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            "PREDICTION",
                            style: GoogleFonts.lexend(
                              fontSize: 9,
                              fontWeight: FontWeight.bold,
                              color: AppColors.textGrey,
                            ),
                          ),
                          Text(
                            prediction,
                            style: GoogleFonts.lexend(
                              fontSize: 12,
                              fontWeight: FontWeight.w800,
                              color: color == AppColors.accentYellow
                                  ? Colors.orange[800]
                                  : color,
                            ),
                          ),
                        ],
                      ),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          Text(
                            "ODDS",
                            style: GoogleFonts.lexend(
                              fontSize: 9,
                              fontWeight: FontWeight.bold,
                              color: AppColors.textGrey,
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 6,
                              vertical: 2,
                            ),
                            decoration: BoxDecoration(
                              color: color,
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Text(
                              odds,
                              style: GoogleFonts.lexend(
                                fontSize: 12,
                                fontWeight: FontWeight.bold,
                                color: color == AppColors.accentYellow
                                    ? Colors.black
                                    : Colors.white,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTeamColumn(String code, String name, bool isDark) {
    return Column(
      children: [
        Container(
          width: 36,
          height: 36,
          decoration: BoxDecoration(
            color: isDark
                ? Colors.white.withValues(alpha: 0.1)
                : Colors.grey[100],
            shape: BoxShape.circle,
            border: Border.all(
              color: isDark
                  ? Colors.white.withValues(alpha: 0.1)
                  : Colors.black.withValues(alpha: 0.05),
            ),
          ),
          child: Center(
            child: Text(
              code,
              style: GoogleFonts.lexend(
                fontSize: 10,
                fontWeight: FontWeight.bold,
                color: AppColors.textGrey,
              ),
            ),
          ),
        ),
        const SizedBox(height: 4),
        Text(
          name,
          style: GoogleFonts.lexend(
            fontSize: 10,
            fontWeight: FontWeight.bold,
            color: isDark ? Colors.white : AppColors.textDark,
          ),
        ),
      ],
    );
  }

  Widget _buildTrendsSection(BuildContext context, bool isDark) {
    return Row(
      children: [
        Expanded(
          child: _buildTrendCard(
            context,
            "HOME WIN %",
            "46%",
            0.46,
            AppColors.primary,
            isDark,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _buildTrendCard(
            context,
            "AVG GOALS",
            "2.84",
            0.70,
            AppColors.accentYellow,
            isDark,
          ),
        ),
      ],
    );
  }

  Widget _buildTrendCard(
    BuildContext context,
    String title,
    String value,
    double progress,
    Color color,
    bool isDark,
  ) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isDark ? AppColors.cardDark : Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isDark
              ? Colors.white.withValues(alpha: 0.05)
              : Colors.black.withValues(alpha: 0.05),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: GoogleFonts.lexend(
              fontSize: 10,
              fontWeight: FontWeight.bold,
              color: AppColors.textGrey,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            value,
            style: GoogleFonts.lexend(
              fontSize: 24,
              fontWeight: FontWeight.w900,
              color: isDark ? Colors.white : AppColors.textDark,
            ),
          ),
          const SizedBox(height: 12),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: progress,
              backgroundColor: isDark
                  ? Colors.white.withValues(alpha: 0.1)
                  : Colors.black.withValues(alpha: 0.05),
              valueColor: AlwaysStoppedAnimation<Color>(color),
              minHeight: 6,
            ),
          ),
        ],
      ),
    );
  }
}
