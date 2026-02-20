// fixtures_tab.dart: fixtures_tab.dart: Widget/screen for App — League Tab Widgets.
// Part of LeoBook App — League Tab Widgets
//
// Classes: LeagueFixturesTab, _LeagueFixturesTabState

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:leobookapp/data/models/match_model.dart';
import 'package:leobookapp/data/repositories/data_repository.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import '../match_card.dart';

class LeagueFixturesTab extends StatefulWidget {
  final String leagueName;
  const LeagueFixturesTab({super.key, required this.leagueName});

  @override
  State<LeagueFixturesTab> createState() => _LeagueFixturesTabState();
}

class _LeagueFixturesTabState extends State<LeagueFixturesTab> {
  late Future<List<MatchModel>> _matchesFuture;

  @override
  void initState() {
    super.initState();
    _matchesFuture = context.read<DataRepository>().fetchMatches();
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<MatchModel>>(
      future: _matchesFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }

        if (snapshot.hasError) {
          return Center(child: Text('Error: ${snapshot.error}'));
        }

        final allMatches = snapshot.data ?? [];
        final matches = allMatches
            .where((m) => m.league == widget.leagueName)
            .toList();

        if (matches.isEmpty) {
          return Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.sports_soccer, size: 48, color: AppColors.textGrey),
                const SizedBox(height: 16),
                Text(
                  "No fixtures found",
                  style: GoogleFonts.lexend(
                    color: AppColors.textGrey,
                    fontSize: 14,
                  ),
                ),
              ],
            ),
          );
        }

        return ListView(
          padding: const EdgeInsets.only(top: 16, bottom: 32),
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    "MATCHDAY 25",
                    style: GoogleFonts.lexend(
                      fontSize: 12,
                      fontWeight: FontWeight.w800,
                      color: AppColors.textGrey,
                      letterSpacing: 1.2,
                    ),
                  ),
                  Text(
                    "FEB 08 - FEB 10",
                    style: GoogleFonts.lexend(
                      fontSize: 10,
                      fontWeight: FontWeight.bold,
                      color: AppColors.primary,
                    ),
                  ),
                ],
              ),
            ),
            ...matches.map((match) => MatchCard(match: match)),
          ],
        );
      },
    );
  }
}
