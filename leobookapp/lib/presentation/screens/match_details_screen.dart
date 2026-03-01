// match_details_screen.dart: match_details_screen.dart: Widget/screen for App  -  Screens.
// Part of LeoBook App  -  Screens
//
// Classes: MatchDetailsScreen, _MatchDetailsScreenState

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/data/models/match_model.dart';
import 'package:leobookapp/data/models/standing_model.dart';
import 'package:leobookapp/data/repositories/data_repository.dart';
import 'package:leobookapp/core/constants/responsive_constants.dart';
import 'team_screen.dart';
import 'league_screen.dart';
import '../widgets/shared/main_top_bar.dart';
import '../widgets/shared/match_card.dart';

class MatchDetailsScreen extends StatefulWidget {
  final MatchModel match;

  const MatchDetailsScreen({super.key, required this.match});

  @override
  State<MatchDetailsScreen> createState() => _MatchDetailsScreenState();
}

class _MatchDetailsScreenState extends State<MatchDetailsScreen> {
  bool _isLoadingIndices = true;
  List<MatchModel> _homeHistory = [];
  List<MatchModel> _awayHistory = [];
  List<MatchModel> _h2hHistory = [];
  List<StandingModel> _standings = [];
  bool _homeExpanded = false;
  bool _awayExpanded = false;
  bool _h2hExpanded = false;

  MatchModel get match => widget.match;

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  Future<void> _loadHistory() async {
    setState(() => _isLoadingIndices = true);
    final repository = context.read<DataRepository>();
    final homeMatches = await repository.getTeamMatches(match.homeTeam);
    final awayMatches = await repository.getTeamMatches(match.awayTeam);

    // Fetch Standings
    List<StandingModel> sTable = [];
    if (match.league != null) {
      sTable = await repository.getStandings(match.league!);
    }

    // Past matches only
    final now = DateTime.now();

    bool isPast(MatchModel m) {
      try {
        final date = DateTime.parse(m.date);
        return date.isBefore(now) || m.status == 'Finished';
      } catch (_) {
        return false;
      }
    }

    final pastHome = homeMatches.where(isPast).take(10).toList();
    final pastAway = awayMatches.where(isPast).take(10).toList();

    // H2H: matches where both teams participated
    final h2h = homeMatches
        .where(
          (m) =>
              (m.homeTeam == match.homeTeam && m.awayTeam == match.awayTeam) ||
              (m.homeTeam == match.awayTeam && m.awayTeam == match.homeTeam),
        )
        .where(isPast)
        .take(10)
        .toList();

    if (mounted) {
      setState(() {
        _homeHistory = pastHome;
        _awayHistory = pastAway;
        _h2hHistory = h2h;
        _standings = sTable;
        _isLoadingIndices = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.backgroundDark,
      body: Column(
        children: [
          MainTopBar(
            currentIndex: -1,
            onTabChanged: (_) {},
          ),
          Expanded(
            child: SingleChildScrollView(
              child: Column(
                children: [
                  // 1. Stadium Header
                  _buildStadiumHeader(context),

                  // Main Content
                  Transform.translate(
                    offset: const Offset(0, -40),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 16),
                      child: Column(
                        children: [
                          // 2. AI Win Probability
                          _buildWinProbabilitySection(),

                          const SizedBox(height: 16),

                          // 3. Expert Prediction
                          _buildExpertPrediction(),

                          const SizedBox(height: 16),

                          // 4. Prediction Insights (all data/stats that led to prediction)
                          _buildPredictionInsights(),

                          const SizedBox(height: 16),

                          // 5. Standings
                          _buildStandingsSection(),

                          const SizedBox(height: 16),

                          // 6. Home Team History
                          _buildMatchHistorySection(
                            "${match.homeTeam}  -  LAST MATCHES",
                            _homeHistory,
                            _homeExpanded,
                            () =>
                                setState(() => _homeExpanded = !_homeExpanded),
                          ),

                          const SizedBox(height: 16),

                          // 7. Away Team History
                          _buildMatchHistorySection(
                            "${match.awayTeam}  -  LAST MATCHES",
                            _awayHistory,
                            _awayExpanded,
                            () =>
                                setState(() => _awayExpanded = !_awayExpanded),
                          ),

                          const SizedBox(height: 16),

                          // 8. H2H History
                          _buildMatchHistorySection(
                            "HEAD-TO-HEAD",
                            _h2hHistory,
                            _h2hExpanded,
                            () => setState(() => _h2hExpanded = !_h2hExpanded),
                          ),

                          const SizedBox(height: 40),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStadiumHeader(BuildContext context) {
    return SizedBox(
      height: 320, // Increased height for better visibility
      child: Stack(
        fit: StackFit.expand,
        children: [
          // Background (Split Colors for Home/Away feel)
          Row(
            children: [
              Expanded(
                child: Container(color: const Color(0xFF0F172A)),
              ), // Slate 900
              Expanded(
                child: Container(color: const Color(0xFF1E293B)),
              ), // Slate 800
            ],
          ),

          // Gradient Overlay
          Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [
                  Colors.transparent,
                  AppColors.backgroundDark.withValues(alpha: 0.8),
                  AppColors.backgroundDark,
                ],
                stops: const [0.0, 0.7, 1.0],
              ),
            ),
          ),

          // Header Actions
          Positioned(
            top: MediaQuery.of(context).padding.top + 10,
            left: 16,
            right: 16,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                CircleAvatar(
                  backgroundColor: Colors.white10,
                  child: IconButton(
                    icon: const Icon(
                      Icons.arrow_back_ios_new,
                      size: 20,
                      color: Colors.white,
                    ),
                    onPressed: () => Navigator.pop(context),
                  ),
                ),
                GestureDetector(
                  onTap: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (context) => LeagueScreen(
                          leagueId: match.league ?? "LEAGUE",
                          leagueName: match.league ?? "LEAGUE",
                        ),
                      ),
                    );
                  },
                  child: Column(
                    children: [
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          if (match.leagueCrestUrl != null &&
                              match.leagueCrestUrl!.isNotEmpty)
                            Padding(
                              padding: const EdgeInsets.only(right: 6),
                              child: CachedNetworkImage(
                                imageUrl: match.leagueCrestUrl!,
                                width: 14,
                                height: 14,
                                fit: BoxFit.contain,
                                errorWidget: (_, __, ___) =>
                                    const SizedBox.shrink(),
                              ),
                            ),
                          Flexible(
                            child: Text(
                              _parseLeagueName(match.league ?? "LEAGUE"),
                              style: GoogleFonts.lexend(
                                color: AppColors.primary,
                                fontSize: 10,
                                fontWeight: FontWeight.bold,
                                letterSpacing: 2.0,
                              ),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 2),
                      Text(
                        "${match.date} | ${match.time}${match.displayStatus.isEmpty ? '' : ' | ${match.displayStatus}'}",
                        style: GoogleFonts.lexend(
                          color: Colors.white60,
                          fontSize: 10,
                        ),
                      ),
                    ],
                  ),
                ),
                CircleAvatar(
                  backgroundColor: Colors.white10,
                  child: IconButton(
                    icon: const Icon(
                      Icons.share,
                      size: 20,
                      color: Colors.white,
                    ),
                    onPressed: () {},
                  ),
                ),
              ],
            ),
          ),

          // Teams Display
          Positioned(
            top: 100,
            left: 0,
            right: 0,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Home Team
                GestureDetector(
                  onTap: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (context) => TeamScreen(
                          teamName: match.homeTeam,
                          repository: context.read<DataRepository>(),
                        ),
                      ),
                    );
                  },
                  child: Column(
                    children: [
                      Container(
                        width: 80,
                        height: 80,
                        decoration: BoxDecoration(
                          color: Colors.white10,
                          borderRadius: BorderRadius.circular(20),
                          border: Border.all(color: Colors.white24),
                        ),
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(18),
                          child: match.homeCrestUrl != null &&
                                  match.homeCrestUrl!.isNotEmpty
                              ? CachedNetworkImage(
                                  imageUrl: match.homeCrestUrl!,
                                  width: 50,
                                  height: 50,
                                  fit: BoxFit.contain,
                                  errorWidget: (_, __, ___) => const Icon(
                                    Icons.shield,
                                    size: 40,
                                    color: Colors.white,
                                  ),
                                )
                              : const Icon(
                                  Icons.shield,
                                  size: 40,
                                  color: Colors.white,
                                ),
                        ),
                      ),
                      const SizedBox(height: 12),
                      Text(
                        match.homeTeam,
                        style: GoogleFonts.lexend(
                          color: Colors.white,
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                        ),
                        textAlign: TextAlign.center,
                      ),
                    ],
                  ),
                ),

                // VS / Badge
                Column(
                  children: [
                    const SizedBox(height: 20),
                    Text(
                      match.displayStatus == "FINISHED" || match.isLive
                          ? "${match.homeScore} : ${match.awayScore}"
                          : "VS",
                      style: GoogleFonts.lexend(
                        color: Colors.white24,
                        fontSize: 32,
                        fontWeight: FontWeight.w900,
                        fontStyle: FontStyle.italic,
                      ),
                    ),
                    const SizedBox(height: 8),
                    if (match.displayStatus.isNotEmpty)
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 10,
                          vertical: 4,
                        ),
                        decoration: BoxDecoration(
                          color: AppColors.primary.withValues(alpha: 0.2),
                          borderRadius: BorderRadius.circular(20),
                          border: Border.all(
                            color: AppColors.primary.withValues(alpha: 0.3),
                          ),
                        ),
                        child: Text(
                          match.displayStatus,
                          style: GoogleFonts.lexend(
                            color: AppColors.primary,
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                  ],
                ),

                // Away Team
                GestureDetector(
                  onTap: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (context) => TeamScreen(
                          teamName: match.awayTeam,
                          repository: context.read<DataRepository>(),
                        ),
                      ),
                    );
                  },
                  child: Column(
                    children: [
                      Container(
                        width: 80,
                        height: 80,
                        decoration: BoxDecoration(
                          color: Colors.white10,
                          borderRadius: BorderRadius.circular(20),
                          border: Border.all(color: Colors.white24),
                        ),
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(18),
                          child: match.awayCrestUrl != null &&
                                  match.awayCrestUrl!.isNotEmpty
                              ? CachedNetworkImage(
                                  imageUrl: match.awayCrestUrl!,
                                  width: 50,
                                  height: 50,
                                  fit: BoxFit.contain,
                                  errorWidget: (_, __, ___) => const Icon(
                                    Icons.shield,
                                    size: 40,
                                    color: Colors.white,
                                  ),
                                )
                              : const Icon(
                                  Icons.shield,
                                  size: 40,
                                  color: Colors.white,
                                ),
                        ),
                      ),
                      const SizedBox(height: 12),
                      Text(
                        match.awayTeam,
                        style: GoogleFonts.lexend(
                          color: Colors.white,
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                        ),
                        textAlign: TextAlign.center,
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

  Widget _buildWinProbabilitySection() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.cardDark,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white10),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.3),
            blurRadius: 20,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                "AI WIN PROBABILITY",
                style: GoogleFonts.lexend(
                  color: Colors.white54,
                  fontSize: 10,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 1.5,
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  "LEO AI MODEL v1.2",
                  style: GoogleFonts.lexend(
                    color: AppColors.primary,
                    fontSize: 10,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          // Progress Bar
          ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: SizedBox(
              height: 24,
              child: Row(
                children: [
                  Expanded(
                    flex: (match.probHome * 100).toInt(),
                    child: Container(
                      color: AppColors.primary,
                      alignment: Alignment.centerLeft,
                      padding: const EdgeInsets.only(left: 8),
                      child: Text(
                        "HOME ${(match.probHome * 100).toInt()}%",
                        style: GoogleFonts.lexend(
                          color: Colors.white,
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ),
                  Expanded(
                    flex: (match.probDraw * 100).toInt(),
                    child: Container(
                      color: Colors.grey[700],
                      alignment: Alignment.center,
                      child: Text(
                        "${(match.probDraw * 100).toInt()}%",
                        style: GoogleFonts.lexend(
                          color: Colors.white,
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ),
                  Expanded(
                    flex: (match.probAway * 100).toInt(),
                    child: Container(
                      color: AppColors.liveRed,
                      alignment: Alignment.centerRight,
                      padding: const EdgeInsets.only(right: 8),
                      child: Text(
                        "${(match.probAway * 100).toInt()}% AWAY",
                        style: GoogleFonts.lexend(
                          color: Colors.white,
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 8),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                match.homeTeam,
                style: GoogleFonts.lexend(
                  color: Colors.white54,
                  fontSize: 9,
                  fontWeight: FontWeight.w500,
                ),
              ),
              Text(
                "Draw",
                style: GoogleFonts.lexend(
                  color: Colors.white54,
                  fontSize: 9,
                  fontWeight: FontWeight.w500,
                ),
              ),
              Text(
                match.awayTeam,
                style: GoogleFonts.lexend(
                  color: Colors.white54,
                  fontSize: 9,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildExpertPrediction() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [AppColors.primary, Colors.blue.shade900],
        ),
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: AppColors.primary.withValues(alpha: 0.3),
            blurRadius: 10,
            offset: const Offset(0, 5),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.psychology, color: Colors.white, size: 20),
              const SizedBox(width: 8),
              Text(
                "EXPERT PREDICTION",
                style: GoogleFonts.lexend(
                  color: Colors.white70,
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 1.2,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    match.prediction ?? "No prediction available",
                    style: GoogleFonts.lexend(
                      color: Colors.white,
                      fontSize: 22,
                      fontWeight: FontWeight.w900,
                      height: 1.1,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    "Confidence: ${match.confidence ?? 'N/A'}",
                    style: GoogleFonts.lexend(
                      color: Colors.white60,
                      fontSize: 11,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 8,
                ),
                decoration: BoxDecoration(
                  color: Colors.white24,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.white24),
                ),
                child: Column(
                  children: [
                    Text(
                      "ODDS",
                      style: GoogleFonts.lexend(
                        color: Colors.white70,
                        fontSize: 9,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    Text(
                      match.odds ?? "-",
                      style: GoogleFonts.lexend(
                        color: Colors.white,
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.black26,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: Colors.white10),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(
                      Icons.analytics,
                      size: 14,
                      color: Colors.cyanAccent,
                    ),
                    const SizedBox(width: 6),
                    Text(
                      "POISSON MODEL ANALYSIS",
                      style: GoogleFonts.lexend(
                        color: Colors.cyanAccent,
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                        letterSpacing: 1.0,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  match.aiReasoningSentence,
                  style: GoogleFonts.lexend(
                    color: Colors.white70,
                    fontSize: 11,
                    fontStyle: FontStyle.italic,
                    height: 1.4,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // â”€â”€ Expandable Match History Section â”€â”€
  Widget _buildMatchHistorySection(
    String title,
    List<MatchModel> matches,
    bool isExpanded,
    VoidCallback onToggle,
  ) {
    if (_isLoadingIndices) {
      return Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: AppColors.cardDark,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: Colors.white10),
        ),
        child: const Center(
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
      );
    }

    final visibleCount = isExpanded
        ? (matches.length > 10 ? 10 : matches.length)
        : (matches.length > 5 ? 5 : matches.length);
    final visibleMatches = matches.take(visibleCount).toList();
    final hasMore = matches.length > 5 && !isExpanded;
    final canCollapse = isExpanded;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.cardDark,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Section Header
          Row(
            children: [
              Icon(
                title.contains("HEAD") ? Icons.compare_arrows : Icons.history,
                size: 16,
                color: AppColors.primary,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  title.toUpperCase(),
                  style: GoogleFonts.lexend(
                    color: AppColors.primary,
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 1.2,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              Text(
                "${matches.length} match${matches.length == 1 ? '' : 'es'}",
                style: GoogleFonts.lexend(
                  color: AppColors.textGrey,
                  fontSize: 10,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),

          if (matches.isEmpty)
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.03),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.white10),
              ),
              child: Center(
                child: Text(
                  "No matches found",
                  style: GoogleFonts.lexend(
                    color: Colors.white24,
                    fontSize: 11,
                  ),
                ),
              ),
            )
          else ...[
            // Match Cards - Responsive Layout
            LayoutBuilder(
              builder: (context, constraints) {
                final isDesktop = Responsive.isDesktop(context);
                if (isDesktop) {
                  const crossAxisCount = 3;
                  const spacing = 12.0;
                  final itemWidth = (constraints.maxWidth -
                          (spacing * (crossAxisCount - 1))) /
                      crossAxisCount;

                  return Wrap(
                    spacing: spacing,
                    runSpacing: spacing,
                    children: visibleMatches
                        .map((m) => SizedBox(
                              width: itemWidth,
                              child: MatchCard(
                                match: m,
                                showLeagueHeader: true,
                                hideLeagueInfo: false,
                              ),
                            ))
                        .toList(),
                  );
                }

                // Mobile/Tablet: Vertical List
                return Column(
                  children: visibleMatches
                      .map((m) => Padding(
                            padding: const EdgeInsets.only(bottom: 8),
                            child: MatchCard(
                              match: m,
                              showLeagueHeader: true,
                              hideLeagueInfo: false,
                            ),
                          ))
                      .toList(),
                );
              },
            ),

            const SizedBox(height: 12),

            // Expand / Collapse Button
            if (hasMore || canCollapse)
              GestureDetector(
                onTap: onToggle,
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(vertical: 10),
                  decoration: BoxDecoration(
                    color: AppColors.primary.withValues(alpha: 0.08),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(
                      color: AppColors.primary.withValues(alpha: 0.2),
                    ),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(
                        isExpanded
                            ? Icons.keyboard_arrow_up
                            : Icons.keyboard_arrow_down,
                        size: 18,
                        color: AppColors.primary,
                      ),
                      const SizedBox(width: 6),
                      Text(
                        isExpanded ? "SHOW LESS" : "SHOW MORE",
                        style: GoogleFonts.lexend(
                          color: AppColors.primary,
                          fontSize: 11,
                          fontWeight: FontWeight.w800,
                          letterSpacing: 0.5,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
          ],
        ],
      ),
    );
  }

  // â”€â”€ Prediction Insights Section â”€â”€
  Widget _buildPredictionInsights() {
    if (match.prediction == null || match.prediction!.isEmpty) {
      return const SizedBox.shrink();
    }

    final List<Map<String, dynamic>> insights = [];

    // xG values
    if (match.xgHome != null && match.xgAway != null) {
      insights.add({
        'icon': Icons.sports_soccer,
        'label': 'Expected Goals (xG)',
        'value':
            '${match.xgHome!.toStringAsFixed(2)}  -  ${match.xgAway!.toStringAsFixed(2)}',
        'sub': '${match.homeTeam} vs ${match.awayTeam}',
      });
    }

    // Win probabilities
    insights.add({
      'icon': Icons.pie_chart_outline,
      'label': 'Win Probability',
      'value':
          'H ${(match.probHome * 100).toInt()}%  |  D ${(match.probDraw * 100).toInt()}%  |  A ${(match.probAway * 100).toInt()}%',
    });

    // Odds
    if (match.odds != null && match.odds!.isNotEmpty && match.odds != '-') {
      insights.add({
        'icon': Icons.monetization_on_outlined,
        'label': 'Market Odds',
        'value': match.odds!,
      });
    }

    // Market reliability
    if (match.marketReliability != null &&
        match.marketReliability!.isNotEmpty) {
      insights.add({
        'icon': Icons.verified_outlined,
        'label': 'Market Reliability',
        'value': match.marketReliability!,
      });
    }

    // Confidence
    if (match.confidence != null && match.confidence!.isNotEmpty) {
      insights.add({
        'icon': Icons.speed,
        'label': 'Confidence Level',
        'value': match.confidence!,
      });
    }

    // Reason tags
    if (match.reasonTags != null && match.reasonTags!.isNotEmpty) {
      insights.add({
        'icon': Icons.label_outline,
        'label': 'Reason Tags',
        'value': match.reasonTags!.replaceAll('|', '  |  '),
      });
    }

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.cardDark,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.insights, size: 16, color: AppColors.primary),
              const SizedBox(width: 8),
              Text(
                "PREDICTION DATA & INSIGHTS",
                style: GoogleFonts.lexend(
                  color: AppColors.primary,
                  fontSize: 11,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 1.2,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ...insights.map((insight) => Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(
                      insight['icon'] as IconData,
                      size: 16,
                      color: AppColors.textGrey.withValues(alpha: 0.7),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            insight['label'] as String,
                            style: GoogleFonts.lexend(
                              color: Colors.white54,
                              fontSize: 10,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            insight['value'] as String,
                            style: GoogleFonts.lexend(
                              color: Colors.white,
                              fontSize: 12,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          if (insight['sub'] != null) ...[
                            const SizedBox(height: 1),
                            Text(
                              insight['sub'] as String,
                              style: GoogleFonts.lexend(
                                color: Colors.white30,
                                fontSize: 9,
                              ),
                            ),
                          ],
                        ],
                      ),
                    ),
                  ],
                ),
              )),
          // AI Reasoning
          const SizedBox(height: 4),
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.03),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.white10),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(
                  Icons.auto_awesome,
                  size: 14,
                  color: Colors.cyanAccent,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    match.aiReasoningSentence,
                    style: GoogleFonts.lexend(
                      color: Colors.white60,
                      fontSize: 10,
                      fontStyle: FontStyle.italic,
                      height: 1.4,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStandingsSection() {
    if (_standings.isEmpty) return const SizedBox.shrink();

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.cardDark,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                "LEAGUE STANDINGS",
                style: GoogleFonts.lexend(
                  color: Colors.white54,
                  fontSize: 10,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 1.5,
                ),
              ),
              GestureDetector(
                onTap: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (context) => LeagueScreen(
                        leagueId: match.league ?? "LEAGUE",
                        leagueName: match.league ?? "LEAGUE",
                      ),
                    ),
                  );
                },
                child: Text(
                  match.league?.toUpperCase() ?? "",
                  style: GoogleFonts.lexend(
                    color: AppColors.primary,
                    fontSize: 9,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: SizedBox(
              width: 500, // Explicit width for horizontal scrolling
              child: Column(
                children: [
                  DefaultTextStyle(
                    style:
                        GoogleFonts.lexend(fontSize: 10, color: Colors.white38),
                    child: const Padding(
                      padding: EdgeInsets.symmetric(vertical: 4),
                      child: Row(
                        children: [
                          SizedBox(width: 25, child: Text("#")),
                          SizedBox(width: 30), // Space for crest
                          Expanded(child: Text("TEAM")),
                          SizedBox(
                              width: 30,
                              child: Text("P", textAlign: TextAlign.center)),
                          SizedBox(
                              width: 30,
                              child: Text("W", textAlign: TextAlign.center)),
                          SizedBox(
                              width: 30,
                              child: Text("D", textAlign: TextAlign.center)),
                          SizedBox(
                              width: 30,
                              child: Text("L", textAlign: TextAlign.center)),
                          SizedBox(
                              width: 35,
                              child: Text("GF", textAlign: TextAlign.center)),
                          SizedBox(
                              width: 35,
                              child: Text("GA", textAlign: TextAlign.center)),
                          SizedBox(
                              width: 35,
                              child: Text("GD", textAlign: TextAlign.center)),
                          SizedBox(
                              width: 45,
                              child: Text("PTS", textAlign: TextAlign.center)),
                        ],
                      ),
                    ),
                  ),
                  const Divider(height: 8, color: Colors.white10),
                  ..._standings.map((s) {
                    final normalizedTableTeam = s.teamName.toLowerCase();
                    final hTeam = match.homeTeam.toLowerCase();
                    final aTeam = match.awayTeam.toLowerCase();

                    final isHome = normalizedTableTeam.contains(hTeam) ||
                        hTeam.contains(normalizedTableTeam);
                    final isAway = normalizedTableTeam.contains(aTeam) ||
                        aTeam.contains(normalizedTableTeam);
                    final isMatchTeam = isHome || isAway;

                    return Padding(
                      padding: const EdgeInsets.symmetric(vertical: 6),
                      child: Row(
                        children: [
                          // Position
                          SizedBox(
                            width: 25,
                            child: Text(
                              s.position.toString(),
                              style: TextStyle(
                                color: isMatchTeam
                                    ? AppColors.primary
                                    : Colors.white70,
                                fontSize: 11,
                                fontWeight: isMatchTeam
                                    ? FontWeight.bold
                                    : FontWeight.normal,
                              ),
                            ),
                          ),
                          // Crest
                          SizedBox(
                            width: 30,
                            child: s.teamCrestUrl != null &&
                                    s.teamCrestUrl != 'Unknown'
                                ? CachedNetworkImage(
                                    imageUrl: s.teamCrestUrl!,
                                    height: 18,
                                    width: 18,
                                    placeholder: (ctx, url) => Container(),
                                    errorWidget: (ctx, url, err) => const Icon(
                                        Icons.shield,
                                        size: 14,
                                        color: Colors.white10),
                                  )
                                : const Icon(Icons.shield,
                                    size: 14, color: Colors.white10),
                          ),
                          // Team Name
                          Expanded(
                            child: GestureDetector(
                              onTap: () {
                                Navigator.push(
                                  context,
                                  MaterialPageRoute(
                                    builder: (context) => TeamScreen(
                                      teamName: s.teamName,
                                      repository:
                                          context.read<DataRepository>(),
                                    ),
                                  ),
                                );
                              },
                              child: Text(
                                s.teamName,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: TextStyle(
                                  color: isMatchTeam
                                      ? AppColors.primary
                                      : Colors.white,
                                  fontSize: 11,
                                  fontWeight: isMatchTeam
                                      ? FontWeight.w900
                                      : FontWeight.normal,
                                ),
                              ),
                            ),
                          ),
                          // Stats
                          SizedBox(
                              width: 30,
                              child: Text(s.played.toString(),
                                  textAlign: TextAlign.center,
                                  style: const TextStyle(
                                      fontSize: 11, color: Colors.white70))),
                          SizedBox(
                              width: 30,
                              child: Text(s.wins.toString(),
                                  textAlign: TextAlign.center,
                                  style: const TextStyle(
                                      fontSize: 11, color: Colors.white70))),
                          SizedBox(
                              width: 30,
                              child: Text(s.draws.toString(),
                                  textAlign: TextAlign.center,
                                  style: const TextStyle(
                                      fontSize: 11, color: Colors.white70))),
                          SizedBox(
                              width: 30,
                              child: Text(s.losses.toString(),
                                  textAlign: TextAlign.center,
                                  style: const TextStyle(
                                      fontSize: 11, color: Colors.white70))),
                          SizedBox(
                              width: 35,
                              child: Text(s.goalsFor.toString(),
                                  textAlign: TextAlign.center,
                                  style: const TextStyle(
                                      fontSize: 11, color: Colors.white70))),
                          SizedBox(
                              width: 35,
                              child: Text(s.goalsAgainst.toString(),
                                  textAlign: TextAlign.center,
                                  style: const TextStyle(
                                      fontSize: 11, color: Colors.white70))),
                          SizedBox(
                              width: 35,
                              child: Text(
                                  (s.goalsFor - s.goalsAgainst).toString(),
                                  textAlign: TextAlign.center,
                                  style: const TextStyle(
                                      fontSize: 11, color: Colors.white70))),
                          // Points
                          SizedBox(
                            width: 45,
                            child: Text(
                              s.points.toString(),
                              textAlign: TextAlign.center,
                              style: TextStyle(
                                color: isMatchTeam
                                    ? AppColors.primary
                                    : Colors.white,
                                fontSize: 11,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),
                        ],
                      ),
                    );
                  }),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  String _parseLeagueName(String leagueStr) {
    if (leagueStr.contains(':')) {
      final parts = leagueStr.split(':');
      if (parts.length >= 2) return parts[1].trim().toUpperCase();
    }
    return leagueStr.toUpperCase();
  }
}
