// search_service.dart: Fuzzy search across teams, leagues, and matches via Supabase.
// Part of LeoBook App — Services
//
// Classes: SearchService

import 'package:flutter/foundation.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

class SearchService {
  final _supabase = Supabase.instance.client;

  /// Search teams and leagues using name matching + search_terms + abbreviations.
  /// Returns a list of maps with keys: id, name, type, crest, region.
  Future<List<Map<String, dynamic>>> fuzzySearch(String query) async {
    final q = query.toLowerCase().trim();
    if (q.isEmpty) return [];

    try {
      final results = <Map<String, dynamic>>[];

      // 1. Search Teams — name, search_terms, abbreviations (all text ILIKE)
      final teamResults = await _supabase
          .from('teams')
          .select('team_id, team_name, team_crest, search_terms, abbreviations')
          .or('team_name.ilike.%$q%,search_terms.ilike.%$q%,abbreviations.ilike.%$q%')
          .limit(10);

      for (var t in (teamResults as List)) {
        results.add({
          'id': t['team_id']?.toString() ?? '',
          'name': t['team_name']?.toString() ?? '',
          'type': 'team',
          'crest': t['team_crest']?.toString() ?? '',
        });
      }

      // 2. Search Leagues (region_league table)
      final leagueResults = await _supabase
          .from('region_league')
          .select(
              'league_id, region, league, league_crest, search_terms, abbreviations')
          .or('league.ilike.%$q%,region.ilike.%$q%,search_terms.ilike.%$q%,abbreviations.ilike.%$q%')
          .limit(10);

      for (var l in (leagueResults as List)) {
        final region = l['region']?.toString() ?? '';
        final league = l['league']?.toString() ?? '';
        final displayName = region.isNotEmpty ? '$region - $league' : league;
        results.add({
          'id': l['league_id']?.toString() ?? '',
          'name': displayName,
          'type': 'league',
          'crest': l['league_crest']?.toString() ?? '',
          'region': region,
        });
      }

      return results;
    } catch (e) {
      debugPrint('[SearchService] Error: $e');
      return [];
    }
  }
}
