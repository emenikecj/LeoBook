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
    final league = json['league'] ?? '';
    String sport = 'Football';

    final l = league.toLowerCase();
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
      match: json['match'] ?? '',
      fixtureId: json['fixture_id']?.toString() ?? '',
      time: json['time'] ?? '',
      date: json['date'] ?? '',
      prediction: json['prediction'] ?? '',
      market: json['market'] ?? '',
      confidence: json['confidence'] ?? '',
      overallAcc: json['overall_acc'] ?? '',
      recentAcc: json['recent_acc'] ?? '',
      trend: json['trend'] ?? '',
      marketOdds:
          (json['market_odds'] as num?)?.toDouble() ??
          (json['odds'] as num?)?.toDouble() ??
          (json['score'] as num?)?.toDouble() ??
          0.0,
      reliabilityScore:
          (json['reliability_score'] as num?)?.toDouble() ??
          (json['score'] as num?)?.toDouble() ??
          0.0,
      league: league,
      sport: sport,
    );
  }
}
