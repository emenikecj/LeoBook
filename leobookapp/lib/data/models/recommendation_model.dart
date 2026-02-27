// recommendation_model.dart: recommendation_model.dart: Widget/screen for App — Data Models.
// Part of LeoBook App — Data Models
//
// Classes: RecommendationModel

class RecommendationModel {
  final String match;
  final String fixtureId;
  final String time;
  final String date;
  final String prediction;
  final String market;
  final String confidence;
  final String overallAcc;
  final String recentAcc;
  final String trend;
  final double marketOdds;
  final double reliabilityScore;
  final String sport;
  final String? homeCrestUrl;
  final String? awayCrestUrl;
  final String league;

  RecommendationModel({
    required this.match,
    required this.fixtureId,
    required this.time,
    required this.date,
    required this.prediction,
    required this.market,
    required this.confidence,
    required this.overallAcc,
    required this.recentAcc,
    required this.trend,
    required this.marketOdds,
    required this.reliabilityScore,
    required this.league,
    this.sport = 'Football',
    this.homeCrestUrl,
    this.awayCrestUrl,
  });

  String get homeTeam {
    if (match.contains(' vs ')) {
      return match.split(' vs ')[0].trim();
    }
    if (match.contains(' - ')) {
      return match.split(' - ')[0].trim();
    }
    return match;
  }

  String get awayTeam {
    if (match.contains(' vs ')) {
      return match.split(' vs ')[1].trim();
    }
    if (match.contains(' - ')) {
      return match.split(' - ')[1].trim();
    }
    return '';
  }

  String get homeShort {
    final t = homeTeam;
    if (t.length <= 3) {
      return t.toUpperCase();
    }
    return t.substring(0, 3).toUpperCase();
  }

  String get awayShort {
    final t = awayTeam;
    if (t.isEmpty) {
      return '???';
    }
    if (t.length <= 3) {
      return t.toUpperCase();
    }
    return t.substring(0, 3).toUpperCase();
  }

  factory RecommendationModel.fromJson(Map<String, dynamic> json) {
    // Standardize column mapping for Supabase 'predictions' table
    final league = json['region_league'] ?? json['league'] ?? '';

    // Create match string if missing (Supabase has home_team, away_team)
    String match = json['match'] ?? '';
    if (match.isEmpty &&
        json['home_team'] != null &&
        json['away_team'] != null) {
      match = "${json['home_team']} vs ${json['away_team']}";
    }

    String sport = 'Football';
    final l = league.toString().toLowerCase();
    if (l.contains('nba') ||
        l.contains('basketball') ||
        l.contains('euroleague')) {
      sport = 'Basketball';
    }
    if (l.contains('atp') ||
        l.contains('wta') ||
        l.contains('itf') ||
        l.contains('tennis')) {
      sport = 'Tennis';
    }

    return RecommendationModel(
      match: match,
      fixtureId: json['fixture_id']?.toString() ?? '',
      time: (json['match_time'] ?? json['time'] ?? '').toString(),
      date: (json['date'] ?? '').toString(),
      prediction: (json['prediction'] ?? '').toString(),
      market: (json['prediction'] ?? json['market'] ?? '').toString(),
      confidence: (json['confidence'] ?? '').toString(),
      overallAcc: (json['overall_acc'] ?? '85%').toString(),
      recentAcc: (json['recent_acc'] ?? '90%').toString(),
      trend: (json['trend'] ?? 'UP').toString(),
      marketOdds: double.tryParse(json['odds']?.toString() ?? '') ??
          double.tryParse(json['market_odds']?.toString() ?? '') ??
          0.0,
      reliabilityScore:
          double.tryParse(json['market_reliability_score']?.toString() ?? '') ??
              double.tryParse(json['reliability_score']?.toString() ?? '') ??
              double.tryParse(json['recommendation_score']?.toString() ?? '') ??
              0.0,
      league: league.toString(),
      sport: sport,
      homeCrestUrl: json['home_crest_url']?.toString(),
      awayCrestUrl: json['away_crest_url']?.toString(),
    );
  }
}
