// home_cubit.dart: home_cubit.dart: Widget/screen for App — State Management (Cubit).
// Part of LeoBook App — State Management (Cubit)
//
// Classes: HomeState, HomeInitial, HomeLoading, HomeLoaded, HomeError, HomeCubit

import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:leobookapp/data/models/match_model.dart';
import 'package:leobookapp/data/repositories/data_repository.dart';

import 'package:leobookapp/data/models/news_model.dart';
import 'package:leobookapp/data/models/recommendation_model.dart';
import 'package:leobookapp/data/repositories/news_repository.dart';

// States
abstract class HomeState {}

class HomeInitial extends HomeState {}

class HomeLoading extends HomeState {}

class HomeLoaded extends HomeState {
  final List<MatchModel> allMatches;
  final List<MatchModel> filteredMatches;
  final List<MatchModel> featuredMatches;
  final List<MatchModel> liveMatches;
  final List<NewsModel> news;
  final List<RecommendationModel> allRecommendations;
  final List<RecommendationModel> filteredRecommendations;
  final DateTime selectedDate;
  final String selectedSport;
  final List<String> availableSports;
  final bool isAllMatchesExpanded;

  // Advanced Filters
  final List<String> selectedLeagues;
  final List<String> selectedPredictionTypes;
  final double minOdds;
  final double maxOdds;

  HomeLoaded({
    required this.allMatches,
    required this.filteredMatches,
    required this.featuredMatches,
    this.liveMatches = const [],
    this.news = const [],
    required this.allRecommendations,
    required this.filteredRecommendations,
    required this.selectedDate,
    this.selectedSport = 'ALL',
    this.availableSports = const ['ALL'],
    this.isAllMatchesExpanded = false,
    this.selectedLeagues = const [],
    this.selectedPredictionTypes = const [],
    this.minOdds = 1.0,
    this.maxOdds = 5.0,
  });
}

class HomeError extends HomeState {
  final String message;
  HomeError(this.message);
}

class HomeCubit extends Cubit<HomeState> {
  final DataRepository _dataRepository;
  final NewsRepository _newsRepository;
  StreamSubscription? _predictionsSub;

  HomeCubit(this._dataRepository, this._newsRepository) : super(HomeInitial());

  Future<void> loadDashboard() async {
    emit(HomeLoading());
    try {
      final now = DateTime.now();

      // Fetch news once
      final news = await _newsRepository.fetchNews();

      // Try fetching predictions for today
      List<MatchModel> matches = await _dataRepository.fetchMatches(date: now);
      List<RecommendationModel> recommendations =
          await _dataRepository.fetchRecommendations();

      DateTime selectionDate = now;

      // If no matches for today, find the most recent date with predictions
      if (matches.isEmpty) {
        final allRecent =
            await _dataRepository.fetchMatches(); // Get latest 200
        if (allRecent.isNotEmpty) {
          final latestDateStr = allRecent
              .map((m) => m.date)
              .reduce((a, b) => a.compareTo(b) > 0 ? a : b);
          selectionDate = DateTime.parse(latestDateStr);
          matches = allRecent.where((m) => m.date == latestDateStr).toList();
        }
      }

      const defaultSport = 'ALL';
      final filteredRecs = _filterRecommendations(
        recommendations,
        selectionDate,
        defaultSport,
      );

      final live = matches.where((m) => m.isLive).toList();

      // Featured logic
      final featured = matches
          .where((m) => m.confidence != null && m.confidence!.contains('High'))
          .toList();

      final sportsSet = {'ALL'};
      for (var m in matches) {
        sportsSet.add(m.sport.toUpperCase());
      }
      for (var r in recommendations) {
        sportsSet.add(r.sport.toUpperCase());
      }
      final availableSports = sportsSet.toList()..sort();

      emit(
        HomeLoaded(
          allMatches: matches,
          filteredMatches: matches,
          featuredMatches: featured,
          liveMatches: live,
          news: news,
          allRecommendations: recommendations,
          filteredRecommendations: filteredRecs,
          selectedDate: selectionDate,
          selectedSport: defaultSport,
          availableSports: availableSports,
          isAllMatchesExpanded: false,
        ),
      );

      // --- Start Realtime Subscriptions ---
      _predictionsSub?.cancel();
      _liveScoresSub?.cancel();
      _predictionsSub = null;
      _liveScoresSub = null;

      _predictionsSub = _dataRepository
          .watchPredictions(date: selectionDate)
          .listen((updatedMatches) {
        _handleRealtimeUpdate(updatedMatches);
      }, onError: (e) {
        debugPrint("Predictions Stream Error: $e");
      });

      _liveScoresSub = _dataRepository.watchLiveScores().listen((liveUpdates) {
        _handleRealtimeUpdate(liveUpdates);
      }, onError: (e) {
        debugPrint("LiveScores Stream Error: $e");
      });
    } catch (e) {
      emit(HomeError("Failed to load dashboard: $e"));
    }
  }

  StreamSubscription? _liveScoresSub;

  void _handleRealtimeUpdate(List<MatchModel> updatedMatches) {
    if (state is HomeLoaded) {
      final currentState = state as HomeLoaded;

      // Merge updated matches into the current state preservation prediction data
      final Map<String, MatchModel> matchMap = {
        for (var m in currentState.allMatches) m.fixtureId: m,
      };

      for (var updated in updatedMatches) {
        final existing = matchMap[updated.fixtureId];
        if (existing != null) {
          matchMap[updated.fixtureId] = existing.mergeWith(updated);
        } else {
          matchMap[updated.fixtureId] = updated;
        }
      }

      final mergedMatches = matchMap.values.toList();

      final filteredMatches = _filterMatches(
        mergedMatches,
        currentState.selectedDate,
        currentState.selectedSport,
        leagues: currentState.selectedLeagues,
        types: currentState.selectedPredictionTypes,
        minO: currentState.minOdds,
        maxO: currentState.maxOdds,
      );

      final live = mergedMatches.where((m) => m.isLive).toList();
      final featured = mergedMatches
          .where((m) => m.confidence != null && m.confidence!.contains('High'))
          .toList();

      emit(
        HomeLoaded(
          allMatches: mergedMatches,
          filteredMatches: filteredMatches,
          featuredMatches: featured,
          liveMatches: live,
          news: currentState.news,
          allRecommendations: currentState.allRecommendations,
          filteredRecommendations: currentState.filteredRecommendations,
          selectedDate: currentState.selectedDate,
          selectedSport: currentState.selectedSport,
          availableSports: currentState.availableSports,
          isAllMatchesExpanded: currentState.isAllMatchesExpanded,
          selectedLeagues: currentState.selectedLeagues,
          selectedPredictionTypes: currentState.selectedPredictionTypes,
          minOdds: currentState.minOdds,
          maxOdds: currentState.maxOdds,
        ),
      );
    }
  }

  void updateDate(DateTime date) async {
    if (state is HomeLoaded) {
      final currentState = state as HomeLoaded;

      // Optionally show a mini-loading state here if desired,
      // but for now we'll just fetch and update.

      final matches = await _dataRepository.fetchMatches(date: date);

      final filteredMatches = _filterMatches(
        matches,
        date,
        currentState.selectedSport,
        leagues: currentState.selectedLeagues,
        types: currentState.selectedPredictionTypes,
        minO: currentState.minOdds,
        maxO: currentState.maxOdds,
      );

      final filteredRecs = _filterRecommendations(
        currentState.allRecommendations,
        date,
        currentState.selectedSport,
        leagues: currentState.selectedLeagues,
        types: currentState.selectedPredictionTypes,
        minO: currentState.minOdds,
        maxO: currentState.maxOdds,
      );

      final featured = filteredMatches
          .where((m) => m.confidence != null && m.confidence!.contains('High'))
          .toList();

      final sportsSet = {'ALL'};
      for (var m in matches) {
        sportsSet.add(m.sport.toUpperCase());
      }
      for (var r in currentState.allRecommendations) {
        sportsSet.add(r.sport.toUpperCase());
      }
      final availableSports = sportsSet.toList()..sort();

      emit(
        HomeLoaded(
          allMatches: matches,
          filteredMatches: filteredMatches,
          featuredMatches: featured,
          liveMatches: matches.where((m) => m.isLive).toList(),
          news: currentState.news,
          allRecommendations: currentState.allRecommendations,
          filteredRecommendations: filteredRecs,
          selectedDate: date,
          selectedSport: currentState.selectedSport,
          availableSports: availableSports,
          isAllMatchesExpanded: false,
          selectedLeagues: currentState.selectedLeagues,
          selectedPredictionTypes: currentState.selectedPredictionTypes,
          minOdds: currentState.minOdds,
          maxOdds: currentState.maxOdds,
        ),
      );

      // Re-subscribe for the new date
      _predictionsSub?.cancel();
      _predictionsSub = null; // Ensure clear

      // Delay slightly to allow the previous channel to leave cleanly
      await Future.delayed(const Duration(milliseconds: 300));

      if (isClosed) return;

      _predictionsSub =
          _dataRepository.watchPredictions(date: date).listen((updatedMatches) {
        _handleRealtimeUpdate(updatedMatches);
      }, onError: (e) {
        debugPrint("Predictions Stream (Update) Error: $e");
      });
    }
  }

  void updateSport(String sport) {
    if (state is HomeLoaded) {
      final currentState = state as HomeLoaded;

      final filteredMatches = _filterMatches(
        currentState.allMatches,
        currentState.selectedDate,
        sport,
        leagues: currentState.selectedLeagues,
        types: currentState.selectedPredictionTypes,
        minO: currentState.minOdds,
        maxO: currentState.maxOdds,
      );
      final filteredRecs = _filterRecommendations(
        currentState.allRecommendations,
        currentState.selectedDate,
        sport,
        leagues: currentState.selectedLeagues,
        types: currentState.selectedPredictionTypes,
        minO: currentState.minOdds,
        maxO: currentState.maxOdds,
      );

      final featured = filteredMatches
          .where((m) => m.confidence != null && m.confidence!.contains('High'))
          .toList();

      emit(
        HomeLoaded(
          allMatches: currentState.allMatches,
          filteredMatches: filteredMatches,
          featuredMatches: featured,
          liveMatches: currentState.liveMatches,
          news: currentState.news,
          allRecommendations: currentState.allRecommendations,
          filteredRecommendations: filteredRecs,
          selectedDate: currentState.selectedDate,
          selectedSport: sport,
          availableSports: currentState.availableSports,
          isAllMatchesExpanded: false,
          selectedLeagues: currentState.selectedLeagues,
          selectedPredictionTypes: currentState.selectedPredictionTypes,
          minOdds: currentState.minOdds,
          maxOdds: currentState.maxOdds,
        ),
      );
    }
  }

  void applyFilters({
    required List<String> leagues,
    required List<String> types,
    required double minOdds,
    required double maxOdds,
  }) {
    if (state is HomeLoaded) {
      final currentState = state as HomeLoaded;

      final filteredMatches = _filterMatches(
        currentState.allMatches,
        currentState.selectedDate,
        currentState.selectedSport,
        leagues: leagues,
        types: types,
        minO: minOdds,
        maxO: maxOdds,
      );
      final filteredRecs = _filterRecommendations(
        currentState.allRecommendations,
        currentState.selectedDate,
        currentState.selectedSport,
        leagues: leagues,
        types: types,
        minO: minOdds,
        maxO: maxOdds,
      );

      final featured = filteredMatches
          .where((m) => m.confidence != null && m.confidence!.contains('High'))
          .toList();

      emit(
        HomeLoaded(
          allMatches: currentState.allMatches,
          filteredMatches: filteredMatches,
          featuredMatches: featured,
          liveMatches: currentState.liveMatches,
          news: currentState.news,
          allRecommendations: currentState.allRecommendations,
          filteredRecommendations: filteredRecs,
          selectedDate: currentState.selectedDate,
          selectedSport: currentState.selectedSport,
          availableSports: currentState.availableSports,
          isAllMatchesExpanded: currentState.isAllMatchesExpanded,
          selectedLeagues: leagues,
          selectedPredictionTypes: types,
          minOdds: minOdds,
          maxOdds: maxOdds,
        ),
      );
    }
  }

  void resetFilters() {
    if (state is HomeLoaded) {
      final currentState = state as HomeLoaded;
      updateSport(
        currentState.selectedSport,
      ); // This will effectively reset if we pass empty filters
    }
  }

  void toggleAllMatchesExpansion() {
    if (state is HomeLoaded) {
      final currentState = state as HomeLoaded;
      emit(
        HomeLoaded(
          allMatches: currentState.allMatches,
          filteredMatches: currentState.filteredMatches,
          featuredMatches: currentState.featuredMatches,
          liveMatches: currentState.liveMatches,
          news: currentState.news,
          allRecommendations: currentState.allRecommendations,
          filteredRecommendations: currentState.filteredRecommendations,
          selectedDate: currentState.selectedDate,
          selectedSport: currentState.selectedSport,
          availableSports: currentState.availableSports,
          isAllMatchesExpanded: !currentState.isAllMatchesExpanded,
        ),
      );
    }
  }

  List<MatchModel> _filterMatches(
    List<MatchModel> matches,
    DateTime date,
    String sport, {
    List<String> leagues = const [],
    List<String> types = const [],
    double minO = 1.0,
    double maxO = 5.0,
  }) {
    final targetDateStr = _formatDateForMatching(date);
    return matches.where((m) {
      final dateMatch = m.date == targetDateStr;
      final sportMatch =
          (sport == 'ALL') || (m.sport.toUpperCase() == sport.toUpperCase());

      bool leagueMatch =
          leagues.isEmpty || (m.league != null && leagues.contains(m.league));
      bool typeMatch = types.isEmpty ||
          (m.prediction != null && types.any((t) => m.prediction!.contains(t)));

      double mOdds = double.tryParse(m.odds ?? '1.0') ?? 1.0;
      bool oddsMatch = mOdds >= minO && mOdds <= maxO;

      return dateMatch && sportMatch && leagueMatch && typeMatch && oddsMatch;
    }).toList();
  }

  List<RecommendationModel> _filterRecommendations(
    List<RecommendationModel> recs,
    DateTime date,
    String sport, {
    List<String> leagues = const [],
    List<String> types = const [],
    double minO = 1.0,
    double maxO = 5.0,
  }) {
    final targetDateStr = _formatDateForMatching(date);
    return recs.where((r) {
      final dateMatch = r.date == targetDateStr;
      final sportMatch =
          (sport == 'ALL') || (r.sport.toUpperCase() == sport.toUpperCase());

      bool leagueMatch = leagues.isEmpty || leagues.contains(r.league);
      bool typeMatch =
          types.isEmpty || types.any((t) => r.prediction.contains(t));

      double rOdds = r.marketOdds;
      bool oddsMatch = rOdds >= minO && rOdds <= maxO;

      return dateMatch && sportMatch && leagueMatch && typeMatch && oddsMatch;
    }).toList();
  }

  String _formatDateForMatching(DateTime date) {
    return "${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}";
  }

  @override
  Future<void> close() async {
    try {
      if (_predictionsSub != null) {
        await _predictionsSub!.cancel();
        _predictionsSub = null;
      }
    } catch (e) {
      debugPrint("Error canceling predictions sub: $e");
    }

    try {
      if (_liveScoresSub != null) {
        await _liveScoresSub!.cancel();
        _liveScoresSub = null;
      }
    } catch (e) {
      debugPrint("Error canceling live scores sub: $e");
    }
    return super.close();
  }
}
