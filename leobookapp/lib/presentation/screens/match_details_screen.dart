// match_details_screen.dart: match_details_screen.dart: Widget/screen for App — Screens.
// Part of LeoBook App — Screens
//
// Classes: MatchDetailsScreen, _MatchDetailsScreenState

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/data/models/match_model.dart';
import 'package:leobookapp/data/models/standing_model.dart';
import 'package:leobookapp/data/repositories/data_repository.dart';
import 'team_screen.dart';
import 'league_screen.dart';
import '../widgets/shared/main_top_bar.dart';

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

    final pastHome = homeMatches.where(isPast).take(5).toList();
    final pastAway = awayMatches.where(isPast).take(5).toList();

    // H2H: matches where both teams participated
    final h2h = homeMatches
        .where(
          (m) =>
              (m.homeTeam == match.homeTeam && m.awayTeam == match.awayTeam) ||
              (m.homeTeam == match.awayTeam && m.awayTeam == match.homeTeam),
        )
        .where(isPast)
        .take(5)
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

                          // 2b. Standings
                          _buildStandingsSection(),

                          const SizedBox(height: 16),

                          // 3. Expert Prediction
                          _buildExpertPrediction(),

                          const SizedBox(height: 16),

                          // 4. Match Stats
                          _buildMatchStats(),

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
                      Text(
                        (match.league ?? "LEAGUE").toUpperCase(),
                        style: GoogleFonts.lexend(
                          color: AppColors.primary,
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                          letterSpacing: 2.0,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        "${match.date} • ${match.time}${match.displayStatus.isEmpty ? '' : ' • ${match.displayStatus}'}",
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
                        child: const Icon(
                          Icons.shield,
                          size: 40,
                          color: Colors.white,
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
                        child: const Icon(
                          Icons.security,
                          size: 40,
                          color: Colors.white,
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

  Widget _buildMatchStats() {
    return Column(
      children: [
        // Title
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Row(
              children: [
                const Icon(
                  Icons.leaderboard,
                  size: 18,
                  color: AppColors.primary,
                ),
                const SizedBox(width: 8),
                Text(
                  "MATCH STATS",
                  style: GoogleFonts.lexend(
                    color: AppColors.primary,
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 1.5,
                  ),
                ),
              ],
            ),
            Text(
              "LAST 5 MATCHES",
              style: GoogleFonts.lexend(
                color: AppColors.textGrey,
                fontSize: 10,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        if (_isLoadingIndices)
          const Center(
            child: Padding(
              padding: EdgeInsets.all(20.0),
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
          )
        else ...[
          Row(
            children: [
              // Home Team Form
              Expanded(
                child: _buildstatBox(
                  "${match.homeTeam} Form",
                  _homeHistory.isEmpty
                      ? Text(
                          "No history",
                          style: GoogleFonts.lexend(
                            color: Colors.white24,
                            fontSize: 10,
                          ),
                        )
                      : Row(
                          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                          children: _homeHistory.map((m) {
                            final hScore = int.tryParse(m.homeScore ?? '') ?? 0;
                            final aScore = int.tryParse(m.awayScore ?? '') ?? 0;
                            final isWin = m.homeTeam == match.homeTeam
                                ? hScore > aScore
                                : aScore > hScore;
                            final isDraw = hScore == aScore;
                            return _buildFormBadge(
                              isWin ? "W" : (isDraw ? "D" : "L"),
                              isWin
                                  ? Colors.green
                                  : (isDraw ? Colors.grey : AppColors.liveRed),
                            );
                          }).toList(),
                        ),
                ),
              ),
              const SizedBox(width: 12),
              // Away Team Form
              Expanded(
                child: _buildstatBox(
                  "${match.awayTeam} Form",
                  _awayHistory.isEmpty
                      ? Text(
                          "No history",
                          style: GoogleFonts.lexend(
                            color: Colors.white24,
                            fontSize: 10,
                          ),
                        )
                      : Row(
                          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                          children: _awayHistory.map((m) {
                            final hScore = int.tryParse(m.homeScore ?? '') ?? 0;
                            final aScore = int.tryParse(m.awayScore ?? '') ?? 0;
                            final isWin = m.homeTeam == match.awayTeam
                                ? hScore > aScore
                                : aScore > hScore;
                            final isDraw = hScore == aScore;
                            return _buildFormBadge(
                              isWin ? "W" : (isDraw ? "D" : "L"),
                              isWin
                                  ? Colors.green
                                  : (isDraw ? Colors.grey : AppColors.liveRed),
                            );
                          }).toList(),
                        ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          // H2H List
          Container(
            decoration: BoxDecoration(
              color: AppColors.cardDark,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: Colors.white10),
            ),
            child: Column(
              children: [
                Padding(
                  padding: const EdgeInsets.all(12.0),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        "HEAD-TO-HEAD HISTORY",
                        style: GoogleFonts.lexend(
                          color: Colors.white54,
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                          letterSpacing: 1.5,
                        ),
                      ),
                      Text(
                        "${_h2hHistory.length} Matches",
                        style: GoogleFonts.lexend(
                          color: AppColors.primary,
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                ),
                const Divider(height: 1, color: Colors.white10),
                if (_h2hHistory.isEmpty)
                  Padding(
                    padding: const EdgeInsets.all(20.0),
                    child: Text(
                      "No direct encounters found",
                      style: GoogleFonts.lexend(
                        color: Colors.white24,
                        fontSize: 11,
                      ),
                    ),
                  )
                else
                  ..._h2hHistory.map((m) {
                    final hScore = int.tryParse(m.homeScore ?? '') ?? 0;
                    final aScore = int.tryParse(m.awayScore ?? '') ?? 0;
                    return Column(
                      children: [
                        _buildH2HRow(
                          m.homeTeam,
                          "$hScore - $aScore",
                          m.awayTeam,
                          hScore > aScore,
                        ),
                        const Divider(height: 1, color: Colors.white10),
                      ],
                    );
                  }),
              ],
            ),
          ),
        ],
      ],
    );
  }

  Widget _buildstatBox(String title, Widget content) {
    return Container(
      height: 80,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.cardDark,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title.toUpperCase(),
            style: GoogleFonts.lexend(
              color: Colors.white54,
              fontSize: 10,
              fontWeight: FontWeight.bold,
            ),
          ),
          Expanded(child: Center(child: content)),
        ],
      ),
    );
  }

  Widget _buildFormBadge(String text, Color color) {
    return Container(
      width: 20,
      height: 20,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        text,
        style: GoogleFonts.lexend(
          color: Colors.white,
          fontSize: 10,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }

  Widget _buildH2HRow(
    String home,
    String score,
    String away,
    bool highlightHome,
  ) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          GestureDetector(
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => TeamScreen(
                    teamName: home,
                    repository: context.read<DataRepository>(),
                  ),
                ),
              );
            },
            child: SizedBox(
              width: 80,
              child: Text(
                home,
                style: GoogleFonts.lexend(
                  color: highlightHome ? Colors.white : Colors.white54,
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
            decoration: BoxDecoration(
              color: highlightHome
                  ? AppColors.primary.withValues(alpha: 0.2)
                  : Colors.white10,
              borderRadius: BorderRadius.circular(4),
            ),
            child: Text(
              score,
              style: GoogleFonts.lexend(
                color: highlightHome ? AppColors.primary : Colors.white70,
                fontSize: 12,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          GestureDetector(
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => TeamScreen(
                    teamName: away,
                    repository: context.read<DataRepository>(),
                  ),
                ),
              );
            },
            child: SizedBox(
              width: 80,
              child: Text(
                away,
                textAlign: TextAlign.end,
                style: GoogleFonts.lexend(
                  color: !highlightHome ? Colors.white : Colors.white54,
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                ),
              ),
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
          DefaultTextStyle(
            style: GoogleFonts.lexend(fontSize: 10, color: Colors.white38),
            child: const Row(
              children: [
                SizedBox(width: 25, child: Text("#")),
                Expanded(child: Text("TEAM")),
                SizedBox(
                  width: 25,
                  child: Text("P", textAlign: TextAlign.center),
                ),
                SizedBox(
                  width: 25,
                  child: Text("W", textAlign: TextAlign.center),
                ),
                SizedBox(
                  width: 25,
                  child: Text("D", textAlign: TextAlign.center),
                ),
                SizedBox(
                  width: 25,
                  child: Text("L", textAlign: TextAlign.center),
                ),
                SizedBox(
                  width: 30,
                  child: Text("GD", textAlign: TextAlign.center),
                ),
                SizedBox(
                  width: 40,
                  child: Text("PTS", textAlign: TextAlign.center),
                ),
              ],
            ),
          ),
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 8),
            child: Divider(height: 1, color: Colors.white10),
          ),
          ..._standings.map((s) {
            final isHome = s.teamName.toLowerCase().contains(
                      match.homeTeam.toLowerCase(),
                    ) ||
                match.homeTeam.toLowerCase().contains(s.teamName.toLowerCase());
            final isAway = s.teamName.toLowerCase().contains(
                      match.awayTeam.toLowerCase(),
                    ) ||
                match.awayTeam.toLowerCase().contains(s.teamName.toLowerCase());
            final isMatchTeam = isHome || isAway;

            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 6),
              child: Row(
                children: [
                  SizedBox(
                    width: 25,
                    child: Text(
                      s.position.toString(),
                      style: TextStyle(
                        color: isMatchTeam ? AppColors.primary : Colors.white70,
                        fontWeight:
                            isMatchTeam ? FontWeight.bold : FontWeight.normal,
                      ),
                    ),
                  ),
                  Expanded(
                    child: GestureDetector(
                      onTap: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (context) => TeamScreen(
                              teamName: s.teamName,
                              repository: context.read<DataRepository>(),
                            ),
                          ),
                        );
                      },
                      child: Text(
                        s.teamName,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          color: isMatchTeam ? AppColors.primary : Colors.white,
                          fontWeight:
                              isMatchTeam ? FontWeight.w900 : FontWeight.normal,
                        ),
                      ),
                    ),
                  ),
                  SizedBox(
                    width: 25,
                    child: Text(
                      s.played.toString(),
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: Colors.white70),
                    ),
                  ),
                  SizedBox(
                    width: 25,
                    child: Text(
                      s.wins.toString(),
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: Colors.white70),
                    ),
                  ),
                  SizedBox(
                    width: 25,
                    child: Text(
                      s.draws.toString(),
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: Colors.white70),
                    ),
                  ),
                  SizedBox(
                    width: 25,
                    child: Text(
                      s.losses.toString(),
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: Colors.white70),
                    ),
                  ),
                  SizedBox(
                    width: 30,
                    child: Text(
                      (s.goalsFor - s.goalsAgainst).toString(),
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: Colors.white70),
                    ),
                  ),
                  SizedBox(
                    width: 40,
                    child: Text(
                      s.points.toString(),
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: isMatchTeam ? AppColors.primary : Colors.white,
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
    );
  }
}
