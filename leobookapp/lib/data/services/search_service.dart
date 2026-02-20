// search_service.dart: search_service.dart: Widget/screen for App — Services.
// Part of LeoBook App — Services
//
// Classes: SearchService

import 'package:supabase_flutter/supabase_flutter.dart';

class SearchService {
  final _supabase = Supabase.instance.client;

  Future<List<Map<String, dynamic>>> fuzzySearch(String query) async {
    final q = query.toLowerCase().trim();
    if (q.isEmpty) return [];

    try {
      // 1. Search Teams where search_terms array contains the query
      // Using 'cs' (contains) filter for exact element match in the enriched array
      final teamResults = await _supabase
          .from('teams')
          .select('id, official_name')
          .filter('search_terms', 'cs', '{"$q"}')
          .limit(5);

      // 2. Search Leagues (region_league)
      final leagueResults = await _supabase
          .from('region_league')
          .select('rl_id, official_name')
          .filter('search_terms', 'cs', '{"$q"}')
          .limit(5);

      // 3. Fallback: If no enriched matches, try basic ILIKE on names
      if (teamResults.isEmpty && leagueResults.isEmpty) {
        final fallbackTeams = await _supabase
            .from('teams')
            .select('id, official_name')
            .ilike('official_name', '%$q%')
            .limit(3);

        final fallbackLeagues = await _supabase
            .from('region_league')
            .select('rl_id, official_name')
            .ilike('official_name', '%$q%')
            .limit(3);

        return [
          ...fallbackTeams.map((t) =>
              {'id': t['id'], 'name': t['official_name'], 'type': 'team'}),
          ...fallbackLeagues.map((l) =>
              {'id': l['rl_id'], 'name': l['official_name'], 'type': 'league'}),
        ];
      }

      return [
        ...teamResults.map(
            (t) => {'id': t['id'], 'name': t['official_name'], 'type': 'team'}),
        ...leagueResults.map((l) =>
            {'id': l['rl_id'], 'name': l['official_name'], 'type': 'league'}),
      ];
    } catch (e) {
      return [];
    }
  }
}
