import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:csv/csv.dart';
import '../../core/constants/api_urls.dart';
import '../models/match_model.dart';
import '../models/recommendation_model.dart';
import '../database/predictions_database.dart';
import 'dart:convert';

class DataRepository {
  static const String _keyRecommended = 'cached_recommended';
  static const String _keyPredictions = 'cached_predictions';

  final PredictionsDatabase _predictionsDb = PredictionsDatabase();

  Future<List<MatchModel>> fetchMatches() async {
    // Use SQLite for mobile/desktop, CSV for web
    if (kIsWeb) {
      return _fetchMatchesFromCsv();
    } else {
      return _fetchMatchesFromDatabase();
    }
  }

  /// SQLite approach for mobile/desktop platforms
  Future<List<MatchModel>> _fetchMatchesFromDatabase() async {
    try {
      // 1. Get database (downloads if not cached)
      await _predictionsDb.getDatabase(ApiUrls.predictionsDb);

      // 2. Query all predictions from database
      final predictions = await _predictionsDb.getAllPredictions();

      debugPrint('Loaded ${predictions.length} predictions from database');

      // 3. Convert database rows to MatchModel objects
      return predictions
          .map((row) {
            // Database row already contains all prediction data
            return MatchModel.fromCsv(row, row);
          })
          .where((m) => m.prediction != null && m.prediction!.isNotEmpty)
          .toList();
    } catch (e) {
      debugPrint("DataRepository Error (Database): $e");

      // Fallback: try to use cached database if download failed
      final isCached = await _predictionsDb.isDatabaseCached();
      if (isCached) {
        try {
          await _predictionsDb.getDatabase(ApiUrls.predictionsDb);
          final predictions = await _predictionsDb.getAllPredictions();
          return predictions
              .map((row) => MatchModel.fromCsv(row, row))
              .where((m) => m.prediction != null && m.prediction!.isNotEmpty)
              .toList();
        } catch (cacheError) {
          debugPrint("Failed to load from cached database: $cacheError");
        }
      }

      return [];
    }
  }

  /// CSV approach for web platform
  Future<List<MatchModel>> _fetchMatchesFromCsv() async {
    final prefs = await SharedPreferences.getInstance();

    try {
      debugPrint('Web platform detected - using CSV approach');

      // 1. Fetch predictions.csv with extended timeout
      final predictionsResponse = await http
          .get(Uri.parse(ApiUrls.predictions))
          .timeout(const Duration(seconds: 180));

      String? predictionsBody;

      if (predictionsResponse.statusCode == 200) {
        predictionsBody = predictionsResponse.body;
        await prefs.setString(_keyPredictions, predictionsBody);
        debugPrint('CSV downloaded and cached successfully');
      } else {
        // Fallback to cache if fetch failed
        predictionsBody = prefs.getString(_keyPredictions);
        debugPrint('Using cached CSV data');
      }

      if (predictionsBody == null) return [];

      // 2. Process Predictions CSV
      List<List<dynamic>> pRows = const CsvToListConverter().convert(
        predictionsBody,
        eol: '\n',
      );

      if (pRows.isEmpty) return [];

      final pHeaders = pRows.first.map((e) => e.toString()).toList();
      final pData = pRows.skip(1).toList();

      final matches = pData
          .where((row) => row.length >= pHeaders.length)
          .map((row) {
            final map = Map<String, dynamic>.fromIterables(pHeaders, row);
            return MatchModel.fromCsv(map, map);
          })
          .where((m) => m.prediction != null && m.prediction!.isNotEmpty)
          .toList();

      debugPrint('Loaded ${matches.length} predictions from CSV');
      return matches;
    } catch (e) {
      debugPrint("DataRepository Error (CSV): $e");

      // Final fallback to cache
      final cachedPredictions = prefs.getString(_keyPredictions);
      if (cachedPredictions != null) {
        try {
          List<List<dynamic>> pRows = const CsvToListConverter().convert(
            cachedPredictions,
            eol: '\n',
          );

          if (pRows.isNotEmpty) {
            final pHeaders = pRows.first.map((e) => e.toString()).toList();
            final pData = pRows.skip(1).toList();

            return pData
                .where((row) => row.length >= pHeaders.length)
                .map((row) {
                  final map = Map<String, dynamic>.fromIterables(pHeaders, row);
                  return MatchModel.fromCsv(map, map);
                })
                .where((m) => m.prediction != null && m.prediction!.isNotEmpty)
                .toList();
          }
        } catch (cacheError) {
          debugPrint("Failed to load from cached CSV: $cacheError");
        }
      }

      return [];
    }
  }

  Future<List<RecommendationModel>> fetchRecommendations() async {
    final prefs = await SharedPreferences.getInstance();
    try {
      final response = await http
          .get(Uri.parse(ApiUrls.recommended))
          .timeout(const Duration(seconds: 30));

      String? body;
      if (response.statusCode == 200) {
        body = utf8.decode(response.bodyBytes);
        await prefs.setString(_keyRecommended, body);
      } else {
        body = prefs.getString(_keyRecommended);
      }

      if (body == null) return [];

      final List<dynamic> jsonList = jsonDecode(body);
      return jsonList
          .map((json) => RecommendationModel.fromJson(json))
          .toList();
    } catch (e) {
      debugPrint("Error fetching recommendations: $e");
      final cached = prefs.getString(_keyRecommended);
      if (cached != null) {
        final List<dynamic> jsonList = jsonDecode(cached);
        return jsonList
            .map((json) => RecommendationModel.fromJson(json))
            .toList();
      }
      return [];
    }
  }
}
