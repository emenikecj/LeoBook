class MatchModel {
  final String date;
  final String time;
  final String homeTeam;
  final String awayTeam;
  final String? homeScore;
  final String? awayScore;
  final String status; // Scheduled, Live, Finished
  final String? prediction;
  final String? odds; // e.g. "1.68"
  final String? confidence; // High/Medium/Low
  final String? league; // e.g. "ENGLAND: Premier League"
  final String sport;

  final String fixtureId; // Key for merging
  final String? liveMinute;
  final bool isFeatured;
  final String? valueTag;

  final String? homeCrestUrl;
  final String? awayCrestUrl;
  final String? regionFlagUrl;
  final String? marketReliability;
  final double? xgHome;
  final double? xgAway;
  final String? reasonTags;
  final int? homeFormN;
  final int? awayFormN;

  final String? homeTeamId;
  final String? awayTeamId;
  final String? outcomeCorrect; // From predictions CSV outcome_correct column

  MatchModel({
    required this.fixtureId,
    required this.date,
    required this.time,
    required this.homeTeam,
    required this.awayTeam,
    this.homeTeamId,
    this.awayTeamId,
    this.homeScore,
    this.awayScore,
    required this.status,
    required this.sport,
    this.league,
    this.prediction,
    this.odds,
    this.confidence,
    this.liveMinute,
    this.isFeatured = false,
    this.valueTag,
    this.homeCrestUrl,
    this.awayCrestUrl,
    this.regionFlagUrl,
    this.marketReliability,
    this.xgHome,
    this.xgAway,
    this.reasonTags,
    this.homeFormN,
    this.awayFormN,
    this.outcomeCorrect,
  });

  String get aiReasoningSentence {
    if (reasonTags == null || reasonTags!.isEmpty) {
      return "AI model currently evaluating match metrics...";
    }

    final tags =
        reasonTags!.split('|').map((t) => t.trim().toLowerCase()).toList();
    List<String> insights = [];

    // Map common tags to sentences
    if (tags.any((t) => t.contains('attack') && t.contains('1'))) {
      insights.add(
        "Home side possesses the league's top-tier offensive output.",
      );
    }
    if (tags.any(
      (t) =>
          t.contains('defense') && (t.contains('weak') || t.contains('poor')),
    )) {
      insights.add(
        "Away team's defensive structure shows significant vulnerability.",
      );
    }
    if (tags.any((t) => t.contains('h2h') && t.contains('dominant'))) {
      insights.add("Historical data shows strong head-to-head dominance.");
    }
    if (tags.any(
      (t) => t.contains('form') && (t.contains('hot') || t.contains('strong')),
    )) {
      insights.add("Current momentum favored by recent strong form.");
    }

    if (xgHome != null && xgAway != null) {
      if (xgHome! > xgAway! + 0.5) {
        insights.add(
          "Underlying xG metrics suggest a clear advantage in chance creation.",
        );
      }
    }

    if (insights.isEmpty) {
      return "Model analysis indicates a high probability for the predicted outcome based on current market trends.";
    }
    return insights.join(" ");
  }

  double get probHome {
    if (xgHome != null && xgAway != null) {
      double total = xgHome! + xgAway! + 0.1;
      return (xgHome! / total) * 0.7 + 0.15; // Normalized with draw padding
    }
    if (homeFormN != null && awayFormN != null) {
      double total = (homeFormN! + awayFormN! + 1).toDouble();
      return (homeFormN! / total) * 0.7 + 0.15;
    }
    return 0.33;
  }

  double get probAway {
    if (xgHome != null && xgAway != null) {
      double total = xgHome! + xgAway! + 0.1;
      return (xgAway! / total) * 0.7 + 0.15;
    }
    if (homeFormN != null && awayFormN != null) {
      double total = (homeFormN! + awayFormN! + 1).toDouble();
      return (awayFormN! / total) * 0.7 + 0.15;
    }
    return 0.33;
  }

  double get probDraw => 1.0 - probHome - probAway;

  bool get isLive {
    final s = status.toLowerCase();
    if (s.contains('finish') || s.contains('ft') || s.contains('finished')) {
      return false;
    }
    if (s.contains('postp') ||
        s.contains('pp') ||
        s.contains('canc') ||
        s.contains('can')) {
      return false;
    }

    try {
      final now = DateTime.now();
      final matchStart = DateTime.parse(
        "${date}T${time.length == 5 ? time : '00:00'}:00",
      );
      final matchEnd = matchStart.add(const Duration(minutes: 150));
      return now.isAfter(matchStart) && now.isBefore(matchEnd);
    } catch (_) {
      return false;
    }
  }

  bool get isFinished {
    final s = status.toLowerCase();
    if (s.contains('finish') ||
        s.contains('ft') ||
        s.contains('finished') ||
        s.contains('full time')) {
      return true;
    }
    // Time-based: if more than 2.5 hours have passed since match start
    try {
      final now = DateTime.now();
      final matchStart = DateTime.parse(
        "${date}T${time.length == 5 ? time : '00:00'}:00",
      );
      final matchEnd = matchStart.add(const Duration(minutes: 150));
      return now.isAfter(matchEnd);
    } catch (_) {
      return false;
    }
  }

  bool get isStartingSoon {
    try {
      final matchDateTime = DateTime.parse(
        "${date}T${time.length == 5 ? time : '00:00'}:00",
      );
      final now = DateTime.now();
      final difference = matchDateTime.difference(now);
      return !difference.isNegative && difference.inHours < 2;
    } catch (_) {
      return false;
    }
  }

  String get displayStatus {
    final s = status.toLowerCase();
    if (isLive) return "LIVE";
    if (s.contains('finish') || s.contains('ft') || s.contains('finished')) {
      return "FINISHED";
    }
    if (s.contains('postp') || s.contains('pp')) return "POSTPONED";
    if (s.contains('canc') || s.contains('can')) return "CANCELED";
    if (s.contains('sched') || s.contains('pending') || s.isEmpty) return "";
    return status.toUpperCase();
  }

  bool get isPredictionAccurate {
    // Prefer outcome_correct from CSV/Supabase when available
    if (outcomeCorrect != null && outcomeCorrect!.isNotEmpty) {
      return outcomeCorrect!.toLowerCase() == 'true';
    }
    // Fallback: compute from scores
    if (homeScore == null || awayScore == null || prediction == null) {
      return false;
    }
    final hs = int.tryParse(homeScore!) ?? 0;
    final as_ = int.tryParse(awayScore!) ?? 0;
    final p = prediction!.toLowerCase();

    if (p.contains('home win')) return hs > as_;
    if (p.contains('away win')) return as_ > hs;
    if (p.contains('draw')) return hs == as_;
    if (p.contains('over 2.5')) return (hs + as_) > 2.5;
    if (p.contains('under 2.5')) return (hs + as_) < 2.5;
    if (p.contains('btts') || p.contains('both teams to score')) {
      return hs > 0 && as_ > 0;
    }
    return false;
  }

  factory MatchModel.fromCsv(
    Map<String, dynamic> row, [
    Map<String, dynamic>? predictionData,
  ]) {
    final fixtureId = row['fixture_id']?.toString() ?? '';
    final matchLink = row['match_link']?.toString() ?? '';
    final dateVal = row['date']?.toString() ?? '';

    // Standardize date to YYYY-MM-DD if in DD.MM.YYYY
    String formattedDate = dateVal;
    if (dateVal.contains('.') && dateVal.split('.').length == 3) {
      final p = dateVal.split('.');
      formattedDate = "${p[2]}-${p[1]}-${p[0]}";
    }

    String sport = 'Football';
    if (matchLink.contains('/basketball/')) sport = 'Basketball';
    if (matchLink.contains('/tennis/')) sport = 'Tennis';
    if (matchLink.contains('/hockey/')) sport = 'Hockey';

    // Parse Score: "2-1" -> home: 2, away: 1
    String? hScore = row['home_score']?.toString();
    String? aScore = row['away_score']?.toString();
    final actualScoreValue = row['actual_score']?.toString();
    if ((hScore == null || hScore.isEmpty) &&
        actualScoreValue != null &&
        actualScoreValue.contains('-')) {
      final parts = actualScoreValue.split('-');
      if (parts.length == 2) {
        hScore = parts[0].trim();
        aScore = parts[1].trim();
      }
    }

    String? prediction;
    String? confidence;
    String? odds;
    String? marketReliability;
    double? xgHome;
    double? xgAway;
    String? reasonTags;
    bool isFeatured = false;

    if (predictionData != null) {
      prediction = predictionData['prediction'];
      confidence = predictionData['confidence'];
      odds = predictionData['odds']?.toString();
      marketReliability =
          predictionData['market_reliability_score']?.toString();
      xgHome = double.tryParse(predictionData['xg_home']?.toString() ?? '');
      xgAway = double.tryParse(predictionData['xg_away']?.toString() ?? '');
      reasonTags = predictionData['reason']?.toString();

      if (confidence != null &&
          (confidence.contains('High') || confidence.contains('Very High'))) {
        isFeatured = true;
      }
    }

    final outcomeCorrect = predictionData?['outcome_correct']?.toString();

    return MatchModel(
      fixtureId: fixtureId,
      date: formattedDate,
      time: row['match_time'] ?? '',
      homeTeam: row['home_team'] ?? '',
      awayTeam: row['away_team'] ?? '',
      homeTeamId: row['home_team_id']?.toString(),
      awayTeamId: row['away_team_id']?.toString(),
      homeScore: hScore,
      awayScore: aScore,
      status: (row['status'] ?? row['match_status'] ?? 'Scheduled').toString(),
      league: row['region_league']?.toString(),
      sport: sport,
      prediction: prediction,
      confidence: confidence,
      odds: odds,
      marketReliability: marketReliability,
      isFeatured: isFeatured,
      homeCrestUrl: row['home_crest_url']?.toString(),
      awayCrestUrl: row['away_crest_url']?.toString(),
      regionFlagUrl: row['region_flag_url']?.toString(),
      xgHome: xgHome,
      xgAway: xgAway,
      reasonTags: reasonTags,
      homeFormN: (row['home_form_n'] as num?)?.toInt(),
      awayFormN: (row['away_form_n'] as num?)?.toInt(),
      outcomeCorrect: outcomeCorrect,
    );
  }
}
