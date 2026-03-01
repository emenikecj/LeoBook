// search_screen.dart: Production-grade search UI with Liquid Glass design.
// Part of LeoBook App — Screens
//
// Classes: SearchScreen, _SearchScreenState

import 'dart:math';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:leobookapp/logic/cubit/search_cubit.dart';
import 'package:leobookapp/logic/cubit/search_state.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/core/constants/responsive_constants.dart';
import 'package:leobookapp/core/widgets/glass_container.dart';
import 'package:leobookapp/data/repositories/data_repository.dart';
import 'package:leobookapp/presentation/screens/team_screen.dart';
import 'package:leobookapp/presentation/screens/league_screen.dart';
import '../widgets/shared/match_card.dart';

class SearchScreen extends StatefulWidget {
  const SearchScreen({super.key});

  @override
  State<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends State<SearchScreen> {
  final TextEditingController _searchController = TextEditingController();
  final FocusNode _focusNode = FocusNode();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _focusNode.requestFocus();
    });
  }

  @override
  void dispose() {
    _searchController.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Scaffold(
      backgroundColor:
          isDark ? AppColors.backgroundDark : AppColors.backgroundLight,
      body: SafeArea(
        child: Column(
          children: [
            // ── Search Bar Header ──
            Padding(
              padding: EdgeInsets.symmetric(
                horizontal: Responsive.sp(context, 12),
                vertical: Responsive.sp(context, 6),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: GlassContainer(
                      borderRadius: Responsive.sp(context, 14),
                      padding: EdgeInsets.zero,
                      interactive: false,
                      child: SizedBox(
                        height: Responsive.sp(context, 40),
                        child: TextField(
                          controller: _searchController,
                          focusNode: _focusNode,
                          onChanged: (val) =>
                              context.read<SearchCubit>().search(val),
                          onSubmitted: (val) {
                            if (val.isNotEmpty) {
                              context.read<SearchCubit>().addRecentSearch(val);
                            }
                          },
                          style: GoogleFonts.lexend(
                            fontSize: Responsive.sp(context, 13),
                            fontWeight: FontWeight.w500,
                            color: isDark ? Colors.white : AppColors.textDark,
                          ),
                          decoration: InputDecoration(
                            hintText: "Search teams, leagues...",
                            hintStyle: GoogleFonts.lexend(
                              fontSize: Responsive.sp(context, 12),
                              color: AppColors.textGrey.withValues(alpha: 0.5),
                            ),
                            prefixIcon: Padding(
                              padding: EdgeInsets.only(
                                  left: Responsive.sp(context, 10),
                                  right: Responsive.sp(context, 6)),
                              child: Icon(
                                Icons.search,
                                size: Responsive.sp(context, 16),
                                color: AppColors.primary,
                              ),
                            ),
                            prefixIconConstraints: const BoxConstraints(),
                            suffixIcon: _searchController.text.isNotEmpty
                                ? GestureDetector(
                                    onTap: () {
                                      _searchController.clear();
                                      context.read<SearchCubit>().search('');
                                    },
                                    child: Padding(
                                      padding: EdgeInsets.only(
                                          right: Responsive.sp(context, 8)),
                                      child: Icon(
                                        Icons.close,
                                        size: Responsive.sp(context, 14),
                                        color: AppColors.textGrey,
                                      ),
                                    ),
                                  )
                                : null,
                            suffixIconConstraints: const BoxConstraints(),
                            border: InputBorder.none,
                            contentPadding: EdgeInsets.symmetric(
                              vertical: Responsive.sp(context, 9),
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                  SizedBox(width: Responsive.sp(context, 10)),
                  GestureDetector(
                    onTap: () => Navigator.pop(context),
                    child: Text(
                      "Cancel",
                      style: GoogleFonts.lexend(
                        color: AppColors.primary,
                        fontWeight: FontWeight.w700,
                        fontSize: Responsive.sp(context, 12),
                      ),
                    ),
                  ),
                ],
              ),
            ),

            // ── Content Area ──
            Expanded(
              child: BlocBuilder<SearchCubit, SearchState>(
                builder: (context, state) {
                  if (state is SearchInitial) {
                    return _buildInitialView(context, state);
                  } else if (state is SearchResults) {
                    return _buildResultsView(context, state);
                  } else if (state is SearchLoading) {
                    return Center(
                      child: SizedBox(
                        width: Responsive.sp(context, 20),
                        height: Responsive.sp(context, 20),
                        child: const CircularProgressIndicator(
                          strokeWidth: 2,
                          color: AppColors.primary,
                        ),
                      ),
                    );
                  }
                  return const SizedBox();
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildInitialView(BuildContext context, SearchInitial state) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return ListView(
      padding: EdgeInsets.symmetric(vertical: Responsive.sp(context, 12)),
      children: [
        // ── Recent Searches ──
        if (state.recentSearches.isNotEmpty) ...[
          Padding(
            padding:
                EdgeInsets.symmetric(horizontal: Responsive.sp(context, 12)),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  "RECENT SEARCHES",
                  style: GoogleFonts.lexend(
                    fontSize: Responsive.sp(context, 9),
                    fontWeight: FontWeight.w900,
                    color: AppColors.textGrey,
                    letterSpacing: 1.2,
                  ),
                ),
                GestureDetector(
                  onTap: () =>
                      context.read<SearchCubit>().clearRecentSearches(),
                  child: Text(
                    "Clear All",
                    style: GoogleFonts.lexend(
                      fontSize: Responsive.sp(context, 10),
                      fontWeight: FontWeight.bold,
                      color: AppColors.primary,
                    ),
                  ),
                ),
              ],
            ),
          ),
          SizedBox(height: Responsive.sp(context, 10)),
          SizedBox(
            height: Responsive.sp(context, 28),
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              padding:
                  EdgeInsets.symmetric(horizontal: Responsive.sp(context, 12)),
              itemCount: state.recentSearches.length,
              itemBuilder: (context, index) {
                final term = state.recentSearches[index];
                return GlassContainer(
                  borderRadius: Responsive.sp(context, 14),
                  padding: EdgeInsets.symmetric(
                      horizontal: Responsive.sp(context, 10)),
                  margin: EdgeInsets.only(right: Responsive.sp(context, 6)),
                  interactive: true,
                  onTap: () {
                    _searchController.text = term;
                    context.read<SearchCubit>().search(term);
                  },
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        Icons.history,
                        size: Responsive.sp(context, 11),
                        color: AppColors.textGrey.withValues(alpha: 0.6),
                      ),
                      SizedBox(width: Responsive.sp(context, 4)),
                      Text(
                        term,
                        style: GoogleFonts.lexend(
                          fontSize: Responsive.sp(context, 10),
                          fontWeight: FontWeight.w500,
                          color: isDark ? Colors.white : AppColors.textDark,
                        ),
                      ),
                      SizedBox(width: Responsive.sp(context, 4)),
                      GestureDetector(
                        onTap: () => context
                            .read<SearchCubit>()
                            .removeRecentSearch(term),
                        child: Icon(
                          Icons.close,
                          size: Responsive.sp(context, 10),
                          color: AppColors.textGrey.withValues(alpha: 0.5),
                        ),
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
          SizedBox(height: Responsive.sp(context, 20)),
        ],

        // ── Popular Teams ──
        Padding(
          padding: EdgeInsets.symmetric(horizontal: Responsive.sp(context, 12)),
          child: Text(
            "POPULAR TEAMS",
            style: GoogleFonts.lexend(
              fontSize: Responsive.sp(context, 9),
              fontWeight: FontWeight.w900,
              color: AppColors.textGrey,
              letterSpacing: 1.2,
            ),
          ),
        ),
        SizedBox(height: Responsive.sp(context, 12)),
        SizedBox(
          height: Responsive.sp(context, 70),
          child: ListView.builder(
            scrollDirection: Axis.horizontal,
            padding:
                EdgeInsets.symmetric(horizontal: Responsive.sp(context, 12)),
            itemCount: state.popularTeams.length,
            itemBuilder: (context, index) {
              final match = state.popularTeams[index];
              return GlassContainer(
                borderRadius: Responsive.sp(context, 14),
                padding: EdgeInsets.all(Responsive.sp(context, 8)),
                margin: EdgeInsets.only(right: Responsive.sp(context, 10)),
                interactive: true,
                onTap: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => TeamScreen(
                        teamName: match.homeTeam,
                        repository: context.read<DataRepository>(),
                      ),
                    ),
                  );
                },
                child: SizedBox(
                  width: Responsive.sp(context, 48),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Container(
                        width: Responsive.sp(context, 34),
                        height: Responsive.sp(context, 34),
                        decoration: BoxDecoration(
                          color: isDark
                              ? Colors.white.withValues(alpha: 0.08)
                              : Colors.grey[100],
                          shape: BoxShape.circle,
                        ),
                        child: Center(
                          child: Text(
                            match.homeTeam
                                .substring(0, min(3, match.homeTeam.length))
                                .toUpperCase(),
                            style: GoogleFonts.lexend(
                              fontSize: Responsive.sp(context, 9),
                              fontWeight: FontWeight.w900,
                              color: AppColors.primary,
                            ),
                          ),
                        ),
                      ),
                      SizedBox(height: Responsive.sp(context, 5)),
                      Text(
                        match.homeTeam,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        textAlign: TextAlign.center,
                        style: GoogleFonts.lexend(
                          fontSize: Responsive.sp(context, 9),
                          fontWeight: FontWeight.bold,
                          color: isDark ? Colors.white : AppColors.textDark,
                        ),
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      ],
    );
  }

  Widget _buildResultsView(BuildContext context, SearchResults state) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    // Separate results by type
    final teams =
        state.searchResults.where((r) => r['type'] == 'team').toList();
    final leagues =
        state.searchResults.where((r) => r['type'] == 'league').toList();

    if (teams.isEmpty && leagues.isEmpty && state.matchedMatches.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.search_off,
              size: Responsive.sp(context, 36),
              color: AppColors.textGrey.withValues(alpha: 0.3),
            ),
            SizedBox(height: Responsive.sp(context, 12)),
            Text(
              "No results for \"${state.query}\"",
              style: GoogleFonts.lexend(
                fontSize: Responsive.sp(context, 13),
                color: AppColors.textGrey,
                fontWeight: FontWeight.w500,
              ),
            ),
            SizedBox(height: Responsive.sp(context, 4)),
            Text(
              "Try a different spelling or search term",
              style: GoogleFonts.lexend(
                fontSize: Responsive.sp(context, 10),
                color: AppColors.textGrey.withValues(alpha: 0.6),
              ),
            ),
          ],
        ),
      );
    }

    return ListView(
      padding: EdgeInsets.symmetric(vertical: Responsive.sp(context, 8)),
      children: [
        // ── TEAMS Section ──
        if (teams.isNotEmpty) ...[
          _buildSectionHeader(context, "TEAMS", Icons.shield_outlined,
              count: teams.length),
          SizedBox(height: Responsive.sp(context, 6)),
          ...teams.map((t) => _buildTeamResultTile(context, t, isDark)),
          SizedBox(height: Responsive.sp(context, 16)),
        ],

        // ── LEAGUES Section ──
        if (leagues.isNotEmpty) ...[
          _buildSectionHeader(context, "LEAGUES", Icons.emoji_events_outlined,
              count: leagues.length),
          SizedBox(height: Responsive.sp(context, 6)),
          ...leagues.map((l) => _buildLeagueResultTile(context, l, isDark)),
          SizedBox(height: Responsive.sp(context, 16)),
        ],

        // ── MATCHES Section ──
        if (state.matchedMatches.isNotEmpty) ...[
          _buildSectionHeader(context, "MATCHES", Icons.sports_soccer_outlined,
              count: state.matchedMatches.length),
          SizedBox(height: Responsive.sp(context, 6)),
          ListView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            padding: EdgeInsets.symmetric(
                horizontal: Responsive.sp(context, 12),
                vertical: Responsive.sp(context, 4)),
            itemCount: state.matchedMatches.length,
            itemBuilder: (context, index) {
              return Padding(
                padding: EdgeInsets.only(bottom: Responsive.sp(context, 8)),
                child: MatchCard(match: state.matchedMatches[index]),
              );
            },
          ),
        ],
      ],
    );
  }

  Widget _buildSectionHeader(BuildContext context, String title, IconData icon,
      {int? count}) {
    return Padding(
      padding: EdgeInsets.symmetric(horizontal: Responsive.sp(context, 12)),
      child: Row(
        children: [
          Icon(icon,
              size: Responsive.sp(context, 13), color: AppColors.primary),
          SizedBox(width: Responsive.sp(context, 6)),
          Text(
            title,
            style: GoogleFonts.lexend(
              fontSize: Responsive.sp(context, 10),
              fontWeight: FontWeight.w900,
              color: AppColors.primary,
              letterSpacing: 1.0,
            ),
          ),
          if (count != null) ...[
            SizedBox(width: Responsive.sp(context, 4)),
            Container(
              padding: EdgeInsets.symmetric(
                horizontal: Responsive.sp(context, 5),
                vertical: Responsive.sp(context, 1),
              ),
              decoration: BoxDecoration(
                color: AppColors.primary.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(Responsive.sp(context, 8)),
              ),
              child: Text(
                count.toString(),
                style: GoogleFonts.lexend(
                  fontSize: Responsive.sp(context, 9),
                  fontWeight: FontWeight.w800,
                  color: AppColors.primary,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildTeamResultTile(
      BuildContext context, Map<String, dynamic> item, bool isDark) {
    final crest = item['crest']?.toString() ?? '';
    final name = item['name']?.toString() ?? '';

    return Padding(
      padding: EdgeInsets.symmetric(
        horizontal: Responsive.sp(context, 12),
        vertical: Responsive.sp(context, 2),
      ),
      child: GlassContainer(
        borderRadius: Responsive.sp(context, 14),
        padding: EdgeInsets.symmetric(
          horizontal: Responsive.sp(context, 12),
          vertical: Responsive.sp(context, 10),
        ),
        interactive: true,
        onTap: () {
          context.read<SearchCubit>().addRecentSearch(name);
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => TeamScreen(
                teamName: name,
                repository: context.read<DataRepository>(),
              ),
            ),
          );
        },
        child: Row(
          children: [
            // Team Badge
            Container(
              width: Responsive.sp(context, 32),
              height: Responsive.sp(context, 32),
              decoration: BoxDecoration(
                color: isDark
                    ? Colors.white.withValues(alpha: 0.08)
                    : AppColors.primary.withValues(alpha: 0.08),
                shape: BoxShape.circle,
              ),
              child: crest.isNotEmpty && crest.startsWith('http')
                  ? ClipOval(
                      child: Image.network(
                        crest,
                        fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) =>
                            _buildTeamInitials(context, name),
                      ),
                    )
                  : _buildTeamInitials(context, name),
            ),
            SizedBox(width: Responsive.sp(context, 10)),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    name,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: GoogleFonts.lexend(
                      fontSize: Responsive.sp(context, 12),
                      fontWeight: FontWeight.w700,
                      color: isDark ? Colors.white : AppColors.textDark,
                    ),
                  ),
                  Text(
                    "Team",
                    style: GoogleFonts.lexend(
                      fontSize: Responsive.sp(context, 9),
                      fontWeight: FontWeight.w500,
                      color: AppColors.textGrey,
                    ),
                  ),
                ],
              ),
            ),
            Icon(
              Icons.chevron_right,
              size: Responsive.sp(context, 14),
              color: AppColors.textGrey.withValues(alpha: 0.5),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildLeagueResultTile(
      BuildContext context, Map<String, dynamic> item, bool isDark) {
    final crest = item['crest']?.toString() ?? '';
    final name = item['name']?.toString() ?? '';
    final region = item['region']?.toString() ?? '';

    return Padding(
      padding: EdgeInsets.symmetric(
        horizontal: Responsive.sp(context, 12),
        vertical: Responsive.sp(context, 2),
      ),
      child: GlassContainer(
        borderRadius: Responsive.sp(context, 14),
        padding: EdgeInsets.symmetric(
          horizontal: Responsive.sp(context, 12),
          vertical: Responsive.sp(context, 10),
        ),
        interactive: true,
        onTap: () {
          context.read<SearchCubit>().addRecentSearch(name);
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => LeagueScreen(
                leagueId: item['id']?.toString() ?? '',
                leagueName: name,
              ),
            ),
          );
        },
        child: Row(
          children: [
            // League Badge
            Container(
              width: Responsive.sp(context, 32),
              height: Responsive.sp(context, 32),
              decoration: BoxDecoration(
                color: isDark
                    ? AppColors.accentYellow.withValues(alpha: 0.12)
                    : AppColors.accentYellow.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(Responsive.sp(context, 8)),
              ),
              child: crest.isNotEmpty && crest.startsWith('http')
                  ? ClipRRect(
                      borderRadius:
                          BorderRadius.circular(Responsive.sp(context, 6)),
                      child: Image.network(
                        crest,
                        fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) => Icon(
                          Icons.emoji_events_outlined,
                          size: Responsive.sp(context, 16),
                          color: AppColors.accentYellow,
                        ),
                      ),
                    )
                  : Icon(
                      Icons.emoji_events_outlined,
                      size: Responsive.sp(context, 16),
                      color: AppColors.accentYellow,
                    ),
            ),
            SizedBox(width: Responsive.sp(context, 10)),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    name,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: GoogleFonts.lexend(
                      fontSize: Responsive.sp(context, 12),
                      fontWeight: FontWeight.w700,
                      color: isDark ? Colors.white : AppColors.textDark,
                    ),
                  ),
                  if (region.isNotEmpty)
                    Text(
                      region,
                      style: GoogleFonts.lexend(
                        fontSize: Responsive.sp(context, 9),
                        fontWeight: FontWeight.w500,
                        color: AppColors.textGrey,
                      ),
                    ),
                ],
              ),
            ),
            Icon(
              Icons.chevron_right,
              size: Responsive.sp(context, 14),
              color: AppColors.textGrey.withValues(alpha: 0.5),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTeamInitials(BuildContext context, String name) {
    return Center(
      child: Text(
        name
            .split(' ')
            .take(2)
            .map((w) => w.isNotEmpty ? w[0] : '')
            .join()
            .toUpperCase(),
        style: GoogleFonts.lexend(
          fontSize: Responsive.sp(context, 10),
          fontWeight: FontWeight.w900,
          color: AppColors.primary,
        ),
      ),
    );
  }
}
