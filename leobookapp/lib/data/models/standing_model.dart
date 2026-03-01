// standing_model.dart: standing_model.dart: Widget/screen for App — Data Models.
// Part of LeoBook App — Data Models
//
// Classes: StandingModel

class StandingModel {
  final String teamName;
  final String? teamId;
  final String? teamCrestUrl;
  final int position;
  final int played;
  final int wins;
  final int draws;
  final int losses;
  final int goalsFor;
  final int goalsAgainst;
  final int points;
  final String? leagueName;

  StandingModel({
    required this.teamName,
    this.teamId,
    this.teamCrestUrl,
    required this.position,
    required this.played,
    required this.wins,
    required this.draws,
    required this.losses,
    required this.goalsFor,
    required this.goalsAgainst,
    required this.points,
    this.leagueName,
  });

  static String _clean(String? text) {
    if (text == null) return "";
    return text
        .replaceAll('â€”', ' - ')
        .replaceAll('â€“', ' - ')
        .replaceAll('â€¢', ' | ')
        .replaceAll('Â', '')
        .trim();
  }

  factory StandingModel.fromJson(Map<String, dynamic> json) {
    return StandingModel(
      teamName: _clean(json['team_name']?.toString() ?? ''),
      teamId: json['team_id']?.toString(),
      teamCrestUrl: json['team_crest']?.toString(),
      position: (json['position'] as num?)?.toInt() ?? 0,
      played: (json['played'] as num?)?.toInt() ?? 0,
      wins: (json['wins'] as num?)?.toInt() ?? 0,
      draws: (json['draws'] as num?)?.toInt() ?? 0,
      losses: (json['losses'] as num?)?.toInt() ?? 0,
      goalsFor: (json['goals_for'] as num?)?.toInt() ?? 0,
      goalsAgainst: (json['goals_against'] as num?)?.toInt() ?? 0,
      points: (json['points'] as num?)?.toInt() ?? 0,
      leagueName: _clean(json['region_league']?.toString() ?? ''),
    );
  }

  double get winRate => played > 0 ? wins / played : 0.0;
  int get goalDiff => goalsFor - goalsAgainst;
}
