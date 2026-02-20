// data_repository.dart: data_repository.dart: Widget/screen for App — Repositories.
// Part of LeoBook App — Repositories
//
// Classes: DataRepository

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:leobookapp/data/models/match_model.dart';
import 'package:leobookapp/data/models/recommendation_model.dart';
import 'package:leobookapp/data/models/standing_model.dart';
import 'dart:convert';
import 'dart:async';

class DataRepository {
  static const String _keyRecommended = 'cached_recommended';
  static const String _keyPredictions = 'cached_predictions';

  final SupabaseClient _supabase = Supabase.instance.client;

  Future<List<MatchModel>> fetchMatches({DateTime? date}) async {
    try {
      var query = _supabase.from('predictions').select();

      if (date != null) {
        final dateStr =
            "${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}";
        query = query.eq('date', dateStr);
      }

      final response = await query.order('date', ascending: false).limit(200);

      debugPrint('Loaded ${response.length} predictions from Supabase');

      // Cache data locally
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_keyPredictions, jsonEncode(response));

      return (response as List)
          .map((row) => MatchModel.fromCsv(row, row))
          .where((m) => m.prediction != null && m.prediction!.isNotEmpty)
          .toList();
    } catch (e) {
      debugPrint("DataRepository Error (Supabase): $e");

      // Fallback to cache
      final prefs = await SharedPreferences.getInstance();
      final cachedString = prefs.getString(_keyPredictions);

      if (cachedString != null) {
        try {
          final List<dynamic> cachedData = jsonDecode(cachedString);
          return cachedData
              .map((row) => MatchModel.fromCsv(row, row))
              .where((m) => m.prediction != null && m.prediction!.isNotEmpty)
              .toList();
        } catch (cacheError) {
          debugPrint("Failed to load from cache: $cacheError");
        }
      }
      return [];
    }
  }

  Future<List<MatchModel>> getTeamMatches(String teamName) async {
    try {
      final response = await _supabase
          .from('predictions')
          .select()
          .or('home_team.eq.$teamName,away_team.eq.$teamName')
          .order('date', ascending: false) // Latest first
          .limit(50); // Limit to last 50 matches

      return (response as List)
          .map((row) => MatchModel.fromCsv(row, row))
          .toList();
    } catch (e) {
      debugPrint("DataRepository Error (Team Matches): $e");
      return [];
    }
  }

  Future<List<RecommendationModel>> fetchRecommendations() async {
    final prefs = await SharedPreferences.getInstance();
    try {
      final response = await _supabase
          .from('predictions')
          .select()
          .eq('is_recommended', true)
          .order('recommendation_score', ascending: false);

      debugPrint('Loaded ${response.length} recommendations from Supabase');

      await prefs.setString(_keyRecommended, jsonEncode(response));

      return (response as List)
          .map((json) => RecommendationModel.fromJson(json))
          .toList();
    } catch (e) {
      debugPrint("Error fetching recommendations (Supabase): $e");
      final cached = prefs.getString(_keyRecommended);
      if (cached != null) {
        try {
          final List<dynamic> jsonList = jsonDecode(cached);
          return jsonList
              .map((json) => RecommendationModel.fromJson(json))
              .toList();
        } catch (cacheError) {
          debugPrint("Failed to load recommendations from cache: $cacheError");
        }
      }
      return [];
    }
  }

  Future<List<StandingModel>> getStandings(String leagueName) async {
    try {
      final response = await _supabase
          .from('standings')
          .select()
          .eq('region_league', leagueName);

      return (response as List)
          .map((row) => StandingModel.fromJson(row))
          .toList();
    } catch (e) {
      debugPrint("DataRepository Error (Standings): $e");
      return [];
    }
  }

  Future<Map<String, String>> fetchTeamCrests() async {
    try {
      final response =
          await _supabase.from('teams').select('team_name, team_crest');
      final Map<String, String> crests = {};
      for (var row in (response as List)) {
        if (row['team_name'] != null && row['team_crest'] != null) {
          crests[row['team_name'].toString()] = row['team_crest'].toString();
        }
      }
      return crests;
    } catch (e) {
      debugPrint("DataRepository Error (Team Crests): $e");
      return {};
    }
  }

  Future<List<MatchModel>> fetchAllSchedules({DateTime? date}) async {
    try {
      var query = _supabase.from('schedules').select();

      if (date != null) {
        final dateStr =
            "${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}";
        query = query.eq('date', dateStr);
      }

      final response = await query.order('date', ascending: false).limit(200);

      return (response as List).map((row) => MatchModel.fromCsv(row)).toList();
    } catch (e) {
      debugPrint("DataRepository Error (Schedules): $e");
      return [];
    }
  }

  Future<StandingModel?> getTeamStanding(String teamName) async {
    try {
      final response = await _supabase
          .from('standings')
          .select()
          .eq('team_name', teamName)
          .maybeSingle();

      if (response != null) {
        return StandingModel.fromJson(response);
      }
      return null;
    } catch (e) {
      debugPrint("DataRepository Error (Team Standing): $e");
      return null;
    }
  }

  // --- Realtime Streams (Postgres Changes Style) ---

  Stream<List<MatchModel>> watchLiveScores() {
    return _supabase.from('live_scores').stream(primaryKey: ['fixture_id']).map(
        (rows) => rows.map((row) => MatchModel.fromCsv(row)).toList());
  }

  Stream<List<MatchModel>> watchPredictions({DateTime? date}) {
    var query =
        _supabase.from('predictions').stream(primaryKey: ['fixture_id']);

    return query.map((rows) {
      var matches = rows.map((row) => MatchModel.fromCsv(row, row)).toList();
      if (date != null) {
        final dateStr =
            "${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}";
        matches = matches.where((m) => m.date == dateStr).toList();
      }
      return matches;
    });
  }
}
