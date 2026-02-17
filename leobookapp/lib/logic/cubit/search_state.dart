import 'package:leobookapp/data/models/match_model.dart';

abstract class SearchState {}

class SearchInitial extends SearchState {
  final List<String> recentSearches;
  final List<MatchModel> popularTeams;

  SearchInitial({this.recentSearches = const [], this.popularTeams = const []});
}

class SearchLoading extends SearchState {}

class SearchResults extends SearchState {
  final String query;
  final List<MatchModel> matchedMatches;
  final List<String> matchedLeagues;
  final List<Map<String, dynamic>> searchResults; // Raw dictionary results
  final List<String> recentSearches;

  SearchResults({
    required this.query,
    required this.matchedMatches,
    required this.matchedLeagues,
    required this.searchResults,
    this.recentSearches = const [],
  });
}

class SearchError extends SearchState {
  final String message;
  SearchError(this.message);
}
