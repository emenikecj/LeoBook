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

      final response = await query.order('date', ascending: false).limit(2000);

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
      // Fetch from predictions
      final predResponse = await _supabase
          .from('predictions')
          .select()
          .or('home_team.eq.$teamName,away_team.eq.$teamName')
          .order('date', ascending: false)
          .limit(40);

      // Fetch from schedules (where historical H2H data is stored)
      final schedResponse = await _supabase
          .from('schedules')
          .select()
          .or('home_team.eq.$teamName,away_team.eq.$teamName')
          .order('date', ascending: false)
          .limit(40);

      final List<MatchModel> matches = [];
      final Set<String> seenIds = {};

      void addMatches(List<dynamic> rows, bool isPrediction) {
        for (var row in rows) {
          final m = isPrediction
              ? MatchModel.fromCsv(row, row)
              : MatchModel.fromCsv(row);

          final id = m.fixtureId;
          if (!seenIds.contains(id)) {
            matches.add(m);
            seenIds.add(id);
          }
        }
      }

      addMatches(predResponse as List, true);
      addMatches(schedResponse as List, false);

      // Enrich matches with crests if missing (schedules table doesn't have them)
      if (matches.isNotEmpty) {
        final crests = await fetchTeamCrests();
        for (int i = 0; i < matches.length; i++) {
          final m = matches[i];
          final hCrest = crests[m.homeTeam] ?? m.homeCrestUrl;
          final aCrest = crests[m.awayTeam] ?? m.awayCrestUrl;
          if ((hCrest != null && hCrest != m.homeCrestUrl) ||
              (aCrest != null && aCrest != m.awayCrestUrl)) {
            matches[i] = m.mergeWith(MatchModel(
              fixtureId: m.fixtureId,
              date: m.date,
              time: m.time,
              homeTeam: m.homeTeam,
              awayTeam: m.awayTeam,
              status: m.status,
              sport: m.sport,
              homeCrestUrl: hCrest ?? m.homeCrestUrl,
              awayCrestUrl: aCrest ?? m.awayCrestUrl,
            ));
          }
        }
      }

      // Sort by date descending
      matches.sort((a, b) {
        try {
          return DateTime.parse(b.date).compareTo(DateTime.parse(a.date));
        } catch (_) {
          return 0;
        }
      });

      return matches;
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
          .gt('recommendation_score', 0)
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
      // Try exact match first
      var response = await _supabase
          .from('standings')
          .select()
          .eq('region_league', leagueName)
          .order('position', ascending: true);

      // Fallback: ILIKE if exact match returns empty (handles format variations)
      if ((response as List).isEmpty && leagueName.isNotEmpty) {
        response = await _supabase
            .from('standings')
            .select()
            .ilike('region_league', '%$leagueName%')
            .order('position', ascending: true);
      }

      // Enrich standings with team crests from teams table
      final standings =
          (response as List).map((row) => StandingModel.fromJson(row)).toList();

      if (standings.isNotEmpty) {
        try {
          final teamNames = standings.map((s) => s.teamName).toList();
          final teamsResponse = await _supabase
              .from('teams')
              .select('team_name, team_crest')
              .inFilter('team_name', teamNames);
          final Map<String, String> crestMap = {};
          for (var row in (teamsResponse as List)) {
            final name = row['team_name']?.toString();
            final crest = row['team_crest']?.toString();
            if (name != null &&
                crest != null &&
                crest.isNotEmpty &&
                crest != 'Unknown') {
              crestMap[name] = crest;
            }
          }
          // Merge crests into standings
          for (int i = 0; i < standings.length; i++) {
            final crest = crestMap[standings[i].teamName];
            if (crest != null && standings[i].teamCrestUrl == null) {
              standings[i] = StandingModel(
                teamName: standings[i].teamName,
                teamId: standings[i].teamId,
                teamCrestUrl: crest,
                position: standings[i].position,
                played: standings[i].played,
                wins: standings[i].wins,
                draws: standings[i].draws,
                losses: standings[i].losses,
                goalsFor: standings[i].goalsFor,
                goalsAgainst: standings[i].goalsAgainst,
                points: standings[i].points,
                leagueName: standings[i].leagueName,
              );
            }
          }
        } catch (e) {
          debugPrint("Could not fetch team crests for standings: $e");
        }
      }

      return standings;
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

      final response = await query.order('date', ascending: false).limit(5000);

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

  Stream<List<MatchModel>> watchSchedules({DateTime? date}) {
    var query = _supabase.from('schedules').stream(primaryKey: ['fixture_id']);

    return query.map((rows) {
      var matches = rows.map((row) => MatchModel.fromCsv(row)).toList();
      if (date != null) {
        final dateStr =
            "${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}";
        matches = matches.where((m) => m.date == dateStr).toList();
      }
      return matches;
    });
  }

  Stream<List<StandingModel>> watchStandings(String leagueName) {
    return _supabase
        .from('standings')
        .stream(primaryKey: ['standings_key'])
        .eq('region_league', leagueName)
        .map((rows) => rows.map((row) => StandingModel.fromJson(row)).toList());
  }

  Stream<Map<String, String>> watchTeamCrestUpdates() {
    return _supabase
        .from('teams')
        .stream(primaryKey: ['team_name']).map((rows) {
      final Map<String, String> crests = {};
      for (var row in rows) {
        if (row['team_name'] != null && row['team_crest'] != null) {
          crests[row['team_name'].toString()] = row['team_crest'].toString();
        }
      }
      return crests;
    });
  }
}
