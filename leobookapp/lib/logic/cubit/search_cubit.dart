import 'package:flutter_bloc/flutter_bloc.dart';
import 'search_state.dart';
import 'package:leobookapp/data/models/match_model.dart';
import 'package:leobookapp/data/models/recommendation_model.dart';
import 'package:leobookapp/data/services/search_service.dart';

class SearchCubit extends Cubit<SearchState> {
  final List<MatchModel> allMatches;
  final List<RecommendationModel> allRecommendations;
  final SearchService _searchService = SearchService();
  List<String> _recentSearches = [];

  SearchCubit({required this.allMatches, required this.allRecommendations})
      : super(
          SearchInitial(
            recentSearches: [],
            popularTeams: _getPopularTeams(allMatches),
          ),
        );

  Future<void> search(String query) async {
    if (query.isEmpty) {
      emit(
        SearchInitial(
          recentSearches: _recentSearches,
          popularTeams: _getPopularTeams(allMatches),
        ),
      );
      return;
    }

    emit(SearchLoading());

    // 1. Get Fuzzy Results from pre-computed Supabase dictionary
    final fuzzyResults = await _searchService.fuzzySearch(query);

    // 2. Map fuzzy results back to local models if possible
    // We filter allMatches based on name matches from the dictionary
    final matchedMatches = allMatches.where((m) {
      final q = query.toLowerCase();
      // Direct contain check as fallback
      bool matches = m.homeTeam.toLowerCase().contains(q) ||
          m.awayTeam.toLowerCase().contains(q) ||
          (m.league?.toLowerCase().contains(q) ?? false);

      // Check if team ID or name is in fuzzy results
      for (var result in fuzzyResults) {
        if (result['type'] == 'team') {
          if (m.homeTeamId == result['id'] || m.awayTeamId == result['id']) {
            matches = true;
          }
        }
      }
      return matches;
    }).toList();

    // 3. Extract Leagues from fuzzy results + matches
    final matchedLeagues = <String>{};
    for (var result in fuzzyResults) {
      if (result['type'] == 'league') {
        matchedLeagues.add(result['name'] as String);
      }
    }
    // Add leagues from matched matches
    for (var m in matchedMatches) {
      if (m.league != null) matchedLeagues.add(m.league!);
    }

    emit(
      SearchResults(
        query: query,
        matchedMatches: matchedMatches,
        matchedLeagues: matchedLeagues.toList(),
        searchResults: fuzzyResults,
        recentSearches: _recentSearches,
      ),
    );
  }

  void addRecentSearch(String query) {
    if (query.trim().isEmpty) return;
    if (!_recentSearches.contains(query)) {
      _recentSearches.insert(0, query);
      if (_recentSearches.length > 5) {
        _recentSearches.removeLast();
      }
    }
  }

  void clearRecentSearches() {
    _recentSearches = [];
    if (state is SearchInitial) {
      emit(
        SearchInitial(
          recentSearches: [],
          popularTeams: (state as SearchInitial).popularTeams,
        ),
      );
    } else if (state is SearchResults) {
      final s = state as SearchResults;
      emit(
        SearchResults(
          query: s.query,
          matchedMatches: s.matchedMatches,
          matchedLeagues: s.matchedLeagues,
          searchResults: s.searchResults,
          recentSearches: [],
        ),
      );
    }
  }

  void removeRecentSearch(String term) {
    _recentSearches.remove(term);
    if (state is SearchInitial) {
      emit(
        SearchInitial(
          recentSearches: List.from(_recentSearches),
          popularTeams: (state as SearchInitial).popularTeams,
        ),
      );
    } else if (state is SearchResults) {
      final s = state as SearchResults;
      emit(
        SearchResults(
          query: s.query,
          matchedMatches: s.matchedMatches,
          matchedLeagues: s.matchedLeagues,
          searchResults: s.searchResults,
          recentSearches: List.from(_recentSearches),
        ),
      );
    }
  }

  static List<MatchModel> _getPopularTeams(List<MatchModel> matches) {
    // Logic: Return first 6 matches to represent "Popular Teams" for demo/reference
    // In real app, this could be based on search frequency
    return matches.take(6).toList();
  }
}
