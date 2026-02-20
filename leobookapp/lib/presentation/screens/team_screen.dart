// team_screen.dart: import 'package:fl_chart/fl_chart.dart'; // Optional for future graph
// Part of LeoBook App — Screens
//
// Classes: TeamScreen, _TeamScreenState

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
// import 'package:fl_chart/fl_chart.dart'; // Optional for future graph
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/data/models/match_model.dart';
import 'package:leobookapp/data/repositories/data_repository.dart';
import '../widgets/shared/match_card.dart';

class TeamScreen extends StatefulWidget {
  final String teamName;
  final String? league;
  final String? logoUrl; // Optional, logic to find logo
  final DataRepository repository;

  const TeamScreen({
    super.key,
    required this.teamName,
    required this.repository,
    this.league,
    this.logoUrl,
  });

  @override
  State<TeamScreen> createState() => _TeamScreenState();
}

class _TeamScreenState extends State<TeamScreen> {
  bool _isLoading = true;
  List<MatchModel> _matches = [];
  List<MatchModel> _pastMatches = [];
  MatchModel? _nextMatch;
  final Map<String, dynamic> _stats = {
    'pos': 'N/A',
    'avgGoals': '0.0',
    'winRate': '0%',
  };
  List<String> _form = []; // W, D, L

  @override
  void initState() {
    super.initState();
    _loadTeamData();
  }

  Future<void> _loadTeamData() async {
    final matches = await widget.repository.getTeamMatches(widget.teamName);
    final standing = await widget.repository.getTeamStanding(widget.teamName);

    // Sort: Future matches (Next) vs Past matches (History)
    final now = DateTime.now();
    final pastMatches = <MatchModel>[];
    final futureMatches = <MatchModel>[];

    for (var m in matches) {
      try {
        final date = DateTime.parse(m.date);
        if (date.isAfter(now) ||
            (date.isAtSameMomentAs(now) && m.displayStatus != 'FINISHED')) {
          futureMatches.add(m);
        } else {
          pastMatches.add(m);
        }
      } catch (e) {
        pastMatches.add(m);
      }
    }

    futureMatches.sort((a, b) => a.date.compareTo(b.date));
    pastMatches.sort(
      (a, b) => b.date.compareTo(a.date),
    ); // Latest first for history

    // Calculate dynamic stats from STANDINGS if available
    if (standing != null) {
      _stats['pos'] = _formatOrdinal(standing.position);
      _stats['winRate'] = "${(standing.winRate * 100).toInt()}%";

      final avgG = standing.played > 0
          ? (standing.goalsFor / standing.played).toStringAsFixed(1)
          : '0.0';
      _stats['avgGoals'] = avgG;
    }

    // Dynamic Form from last 5 matches
    _form = pastMatches.take(5).map((m) {
      final hScore = int.tryParse(m.homeScore ?? '') ?? 0;
      final aScore = int.tryParse(m.awayScore ?? '') ?? 0;
      if (hScore == aScore) return 'D';
      if (m.homeTeam == widget.teamName) {
        return hScore > aScore ? 'W' : 'L';
      } else {
        return aScore > hScore ? 'W' : 'L';
      }
    }).toList();

    if (mounted) {
      setState(() {
        _matches = [...futureMatches, ...pastMatches];
        _pastMatches = pastMatches;
        _nextMatch = futureMatches.isNotEmpty ? futureMatches.first : null;
        _isLoading = false;
      });
    }
  }

  String _formatOrdinal(int n) {
    if (n == 0) return 'N/A';
    final j = n % 10, k = n % 100;
    if (j == 1 && k != 11) return "${n}st";
    if (j == 2 && k != 12) return "${n}nd";
    if (j == 3 && k != 13) return "${n}rd";
    return "${n}th";
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.backgroundDark,
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : CustomScrollView(
              slivers: [
                _buildSliverAppBar(),
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16.0),
                    child: Column(
                      children: [
                        const SizedBox(height: 20),
                        _buildStatsGrid(),
                        const SizedBox(height: 30),
                        _buildRecentForm(),
                        const SizedBox(height: 30),
                        if (_nextMatch != null) _buildNextMatch(_nextMatch!),
                        const SizedBox(height: 30),
                        _buildMatchList(),
                        const SizedBox(height: 40),
                      ],
                    ),
                  ),
                ),
              ],
            ),
    );
  }

  Widget _buildSliverAppBar() {
    return SliverAppBar(
      expandedHeight: 250.0,
      floating: false,
      pinned: true,
      backgroundColor: AppColors.backgroundDark.withValues(alpha: 0.8),
      flexibleSpace: FlexibleSpaceBar(
        background: Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [
                AppColors.primary.withValues(alpha: 0.15),
                AppColors.backgroundDark,
              ],
            ),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const SizedBox(height: 40),
              Stack(
                children: [
                  Container(
                    width: 80,
                    height: 80,
                    decoration: BoxDecoration(
                      color: AppColors.cardDark,
                      shape: BoxShape.circle,
                      border: Border.all(color: Colors.white12, width: 4),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black45,
                          blurRadius: 10,
                          offset: const Offset(0, 5),
                        ),
                      ],
                    ),
                    child: const Icon(
                      Icons.shield,
                      size: 40,
                      color: AppColors.primary,
                    ),
                  ),
                  Positioned(
                    bottom: 0,
                    right: 0,
                    child: Container(
                      padding: const EdgeInsets.all(2),
                      decoration: const BoxDecoration(
                        color: AppColors.successGreen,
                        shape: BoxShape.circle,
                      ),
                      child: const Icon(
                        Icons.check,
                        size: 12,
                        color: Colors.white,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Text(
                widget.teamName,
                style: GoogleFonts.lexend(
                  fontSize: 24,
                  fontWeight: FontWeight.w900,
                  color: Colors.white,
                ),
              ),
              Text(
                widget.league ??
                    (_matches.isNotEmpty
                        ? _matches.first.league ?? ''
                        : 'League'),
                style: GoogleFonts.lexend(
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                  color: AppColors.textGrey,
                  letterSpacing: 1.5,
                ),
              ),
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 24,
                  vertical: 10,
                ),
                decoration: BoxDecoration(
                  color: AppColors.primary,
                  borderRadius: BorderRadius.circular(30),
                  boxShadow: [
                    BoxShadow(
                      color: AppColors.primary.withValues(alpha: 0.3),
                      blurRadius: 12,
                      offset: const Offset(0, 4),
                    ),
                  ],
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(
                      Icons.notifications_none,
                      size: 16,
                      color: Colors.white,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      "Follow",
                      style: GoogleFonts.lexend(
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
      leading: IconButton(
        icon: const Icon(
          Icons.arrow_back_ios_new,
          size: 20,
          color: AppColors.primary,
        ),
        onPressed: () => Navigator.pop(context),
      ),
      actions: [
        IconButton(
          icon: const Icon(Icons.share, size: 20, color: AppColors.textGrey),
          onPressed: () {},
        ),
      ],
    );
  }

  Widget _buildStatsGrid() {
    return GridView.count(
      crossAxisCount: 3,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: 12,
      crossAxisSpacing: 12,
      childAspectRatio: 1.3,
      children: [
        _buildStatCard("LEAGUE POS.", _stats['pos']),
        _buildStatCard("AVG. GOALS", _stats['avgGoals']),
        _buildStatCard("PRED. WIN", _stats['winRate']),
      ],
    );
  }

  Widget _buildStatCard(String label, String value) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.cardDark.withValues(alpha: 0.6),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white12),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(
            label,
            style: GoogleFonts.lexend(
              fontSize: 9,
              fontWeight: FontWeight.bold,
              color: AppColors.textGrey,
              letterSpacing: 0.5,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            value,
            style: GoogleFonts.lexend(
              fontSize: 18,
              fontWeight: FontWeight.w900,
              color: AppColors.accentBlue,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRecentForm() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          "RECENT FORM",
          style: GoogleFonts.lexend(
            fontSize: 12,
            fontWeight: FontWeight.bold,
            color: AppColors.textGrey,
            letterSpacing: 1.2,
          ),
        ),
        const SizedBox(height: 12),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
          children: _form.map((result) {
            Color color;
            if (result == 'W') {
              color = AppColors.successGreen;
            } else if (result == 'L') {
              color = AppColors.liveRed;
            } else {
              color = AppColors.textGrey;
            }

            return Column(
              children: [
                Container(
                  width: 36,
                  height: 36,
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.15),
                    shape: BoxShape.circle,
                    border: Border.all(color: color.withValues(alpha: 0.3)),
                  ),
                  child: Center(
                    child: Text(
                      result,
                      style: GoogleFonts.lexend(
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                        color: color,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  _form.indexOf(result) < _pastMatches.length
                      ? (_pastMatches[_form.indexOf(result)].homeTeam ==
                                widget.teamName
                            ? _pastMatches[_form.indexOf(result)].awayTeam
                            : _pastMatches[_form.indexOf(result)].homeTeam)
                      : "OPP",
                  style: GoogleFonts.lexend(
                    fontSize: 8,
                    fontWeight: FontWeight.bold,
                    color: AppColors.textGrey,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            );
          }).toList(),
        ),
      ],
    );
  }

  Widget _buildNextMatch(MatchModel match) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(Icons.psychology, size: 18, color: AppColors.primary),
            const SizedBox(width: 8),
            Text(
              "NEXT MATCH PREDICTION",
              style: GoogleFonts.lexend(
                fontSize: 12,
                fontWeight: FontWeight.bold,
                color: AppColors.textGrey,
                letterSpacing: 1.2,
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Container(
          decoration: BoxDecoration(
            color: AppColors.cardDark,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.primary.withValues(alpha: 0.3)),
            boxShadow: [
              BoxShadow(
                color: Colors.black26,
                blurRadius: 15,
                offset: const Offset(0, 5),
              ),
            ],
          ),
          child: Column(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 8,
                ),
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.1),
                  border: Border(
                    bottom: BorderSide(
                      color: AppColors.primary.withValues(alpha: 0.1),
                    ),
                  ),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      match.league ?? "LEAGUE",
                      style: const TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                        color: AppColors.primary,
                      ),
                    ),
                    Text(
                      "${match.date} • ${match.time}",
                      style: const TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textGrey,
                      ),
                    ),
                  ],
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        _buildTeamColumn(match.homeTeam),
                        const Text(
                          "VS",
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w900,
                            color: Colors.white24,
                            fontStyle: FontStyle.italic,
                          ),
                        ),
                        _buildTeamColumn(match.awayTeam),
                      ],
                    ),
                    const SizedBox(height: 20),
                    Row(
                      children: [
                        Expanded(
                          child: Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: AppColors.backgroundDark.withValues(
                                alpha: 0.5,
                              ),
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(color: Colors.white10),
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text(
                                  "PREDICTION",
                                  style: TextStyle(
                                    fontSize: 9,
                                    fontWeight: FontWeight.bold,
                                    color: AppColors.textGrey,
                                  ),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  match.prediction ?? "N/A",
                                  style: const TextStyle(
                                    fontSize: 13,
                                    fontWeight: FontWeight.bold,
                                    color: AppColors.primary,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Container(
                          width: 70,
                          height: 56, // Match height roughly
                          decoration: BoxDecoration(
                            color: AppColors.primary,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const Text(
                                "ODDS",
                                style: TextStyle(
                                  fontSize: 9,
                                  fontWeight: FontWeight.bold,
                                  color: Colors.white70,
                                ),
                              ),
                              Text(
                                match.odds ?? "-",
                                style: const TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.w900,
                                  color: Colors.white,
                                ),
                              ),
                            ],
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
    );
  }

  Widget _buildTeamColumn(String name) {
    return Column(
      children: [
        Container(
          width: 48,
          height: 48,
          decoration: BoxDecoration(
            color: AppColors.backgroundDark,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: Colors.white10),
          ),
          child: const Icon(Icons.shield, color: AppColors.textGrey, size: 24),
        ),
        const SizedBox(height: 8),
        Text(
          name,
          style: const TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.bold,
            color: Colors.white,
          ),
        ),
      ],
    );
  }

  Widget _buildMatchList() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(
              Icons.calendar_month,
              size: 18,
              color: AppColors.primary,
            ),
            const SizedBox(width: 8),
            Text(
              "ALL MATCHES",
              style: GoogleFonts.lexend(
                fontSize: 12,
                fontWeight: FontWeight.bold,
                color: AppColors.textGrey,
                letterSpacing: 1.2,
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        ..._matches.map(
          (m) => Padding(
            padding: const EdgeInsets.only(bottom: 8.0),
            child: MatchCard(match: m),
          ),
        ),
      ],
    );
  }
}
