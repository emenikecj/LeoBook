import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:leobookapp/logic/cubit/search_cubit.dart';
import 'package:leobookapp/logic/cubit/search_state.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/data/repositories/data_repository.dart';
import 'package:leobookapp/presentation/screens/team_screen.dart';
import 'package:leobookapp/presentation/screens/league_screen.dart';
import '../widgets/match_card.dart';

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
            // Header with Search Bar
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Row(
                children: [
                  Expanded(
                    child: Container(
                      height: 48,
                      decoration: BoxDecoration(
                        color: isDark ? AppColors.cardDark : Colors.white,
                        borderRadius: BorderRadius.circular(24),
                        border: Border.all(color: AppColors.primary, width: 2),
                      ),
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
                        style: const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w500,
                        ),
                        decoration: InputDecoration(
                          hintText: "Search teams, leagues, players...",
                          hintStyle: TextStyle(
                            color: AppColors.textGrey.withValues(alpha: 0.5),
                          ),
                          prefixIcon: const Icon(
                            Icons.search,
                            color: AppColors.primary,
                          ),
                          border: InputBorder.none,
                          contentPadding: const EdgeInsets.symmetric(
                            vertical: 11,
                          ),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  GestureDetector(
                    onTap: () => Navigator.pop(context),
                    child: const Text(
                      "Cancel",
                      style: TextStyle(
                        color: AppColors.primary,
                        fontWeight: FontWeight.w600,
                        fontSize: 14,
                      ),
                    ),
                  ),
                ],
              ),
            ),

            Expanded(
              child: BlocBuilder<SearchCubit, SearchState>(
                builder: (context, state) {
                  if (state is SearchInitial) {
                    return _buildInitialView(context, state);
                  } else if (state is SearchResults) {
                    return _buildResultsView(context, state);
                  } else if (state is SearchLoading) {
                    return const Center(child: CircularProgressIndicator());
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
      padding: const EdgeInsets.symmetric(vertical: 16),
      children: [
        if (state.recentSearches.isNotEmpty) ...[
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  "RECENT SEARCHES",
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w900,
                    color: AppColors.textGrey,
                    letterSpacing: 1.2,
                  ),
                ),
                GestureDetector(
                  onTap: () =>
                      context.read<SearchCubit>().clearRecentSearches(),
                  child: const Text(
                    "Clear All",
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                      color: AppColors.primary,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          SizedBox(
            height: 36,
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 16),
              itemCount: state.recentSearches.length,
              itemBuilder: (context, index) {
                final term = state.recentSearches[index];
                return Container(
                  margin: const EdgeInsets.only(right: 8),
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  decoration: BoxDecoration(
                    color: isDark ? AppColors.cardDark : Colors.white,
                    borderRadius: BorderRadius.circular(18),
                    border: Border.all(
                      color: isDark
                          ? Colors.white.withValues(alpha: 0.05)
                          : Colors.black.withValues(alpha: 0.05),
                    ),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        term,
                        style: const TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                      const SizedBox(width: 4),
                      GestureDetector(
                        onTap: () => context
                            .read<SearchCubit>()
                            .removeRecentSearch(term),
                        child: Icon(
                          Icons.close,
                          size: 14,
                          color: AppColors.textGrey.withValues(alpha: 0.6),
                        ),
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
          const SizedBox(height: 32),
        ],
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: const Text(
            "POPULAR TEAMS",
            style: TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w900,
              color: AppColors.textGrey,
              letterSpacing: 1.2,
            ),
          ),
        ),
        const SizedBox(height: 16),
        SizedBox(
          height: 90,
          child: ListView.builder(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            itemCount: state.popularTeams.length,
            itemBuilder: (context, index) {
              final match = state.popularTeams[index];
              return Container(
                width: 65,
                margin: const EdgeInsets.only(right: 16),
                child: Column(
                  children: [
                    Container(
                      width: 50,
                      height: 50,
                      decoration: BoxDecoration(
                        color: isDark ? AppColors.cardDark : Colors.white,
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: isDark
                              ? Colors.white.withValues(alpha: 0.05)
                              : Colors.black.withValues(alpha: 0.05),
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.black.withValues(alpha: 0.05),
                            blurRadius: 4,
                            offset: const Offset(0, 2),
                          ),
                        ],
                      ),
                      child: Center(
                        child: Text(
                          match.homeTeam
                              .substring(0, min(3, match.homeTeam.length))
                              .toUpperCase(),
                          style: const TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w900,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      match.homeTeam,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              );
            },
          ),
        ),
      ],
    );
  }

  Widget _buildResultsView(BuildContext context, SearchResults state) {
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
              size: 48,
              color: AppColors.textGrey.withValues(alpha: 0.3),
            ),
            const SizedBox(height: 16),
            Text(
              "No results found for \"${state.query}\"",
              style: TextStyle(
                color: AppColors.textGrey,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
      );
    }

    return ListView(
      padding: const EdgeInsets.symmetric(vertical: 16),
      children: [
        // --- MATCHED TEAMS ---
        if (teams.isNotEmpty) ...[
          _buildSectionHeader("TEAMS"),
          ...teams.map((t) => _buildSearchResultItem(context, t, Icons.shield)),
          const SizedBox(height: 24),
        ],

        // --- MATCHED LEAGUES ---
        if (leagues.isNotEmpty) ...[
          _buildSectionHeader("LEAGUES"),
          ...leagues.map(
              (l) => _buildSearchResultItem(context, l, Icons.emoji_events)),
          const SizedBox(height: 24),
        ],

        // --- MATCHES ---
        if (state.matchedMatches.isNotEmpty) ...[
          _buildSectionHeader("MATCHES"),
          ListView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            itemCount: state.matchedMatches.length,
            itemBuilder: (context, index) {
              return Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: MatchCard(match: state.matchedMatches[index]),
              );
            },
          ),
        ],
      ],
    );
  }

  Widget _buildSectionHeader(String title) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Text(
        title,
        style: const TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w900,
          color: AppColors.primary,
          letterSpacing: 1.2,
        ),
      ),
    );
  }

  Widget _buildSearchResultItem(
      BuildContext context, Map<String, dynamic> item, IconData icon) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return GestureDetector(
      onTap: () {
        if (item['type'] == 'team') {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => TeamScreen(
                teamName: item['name'],
                repository: context.read<DataRepository>(),
              ),
            ),
          );
        } else if (item['type'] == 'league') {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => LeagueScreen(
                leagueId: item['id'].toString(),
                leagueName: item['name'],
              ),
            ),
          );
        }
        // Save to recent searches
        context.read<SearchCubit>().addRecentSearch(item['name']);
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: isDark ? AppColors.cardDark : Colors.white,
          border: Border(
            bottom: BorderSide(
              color: isDark
                  ? Colors.white.withValues(alpha: 0.05)
                  : Colors.black.withValues(alpha: 0.05),
            ),
          ),
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: AppColors.backgroundDark,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(icon, size: 16, color: AppColors.textGrey),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                item['name'],
                style:
                    const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
              ),
            ),
            const Icon(Icons.chevron_right,
                size: 16, color: AppColors.textGrey),
          ],
        ),
      ),
    );
  }

  int min(int a, int b) => a < b ? a : b;
}
