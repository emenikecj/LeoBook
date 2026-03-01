// match_model.dart: match_model.dart: Widget/screen for App — Data Models.
// Part of LeoBook App — Data Models
//
// Classes: MatchModel

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
  final String? leagueCrestUrl;
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
    this.leagueCrestUrl,
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
    // Status-only check — 2.5hr time rule deprecated (v3)
    if (s.contains('live') ||
        s.contains('in-play') ||
        s.contains('halftime') ||
        s.contains('ht') ||
        s.contains('penalties') ||
        s.contains('extra_time') ||
        s.contains('break')) {
      return true;
    }
    return false;
  }

  bool get isFinished {
    final s = status.toLowerCase();
    // Status-only check — recognizes regular finish, AET, and penalties
    // IMPORTANT: avoid substring traps — 'pen' matches 'pending'/'suspended'
    if (s.contains('finish') ||
        s == 'ft' ||
        s.contains('full time') ||
        s.contains('aet') ||
        s.contains('after et') ||
        s == 'penalties' ||
        s.contains('after pen') ||
        s.contains('fro')) {
      return true;
    }
    return false;
  }

  bool get isPostponed {
    final s = status.toLowerCase();
    return s.contains('postp') || s.contains('pp');
  }

  bool get isCancelled {
    final s = status.toLowerCase();
    return s.contains('canc') ||
        s.contains('cancelled') ||
        s.contains('abandoned') ||
        s.contains('abn');
  }

  bool get isFrozen {
    final s = status.toLowerCase();
    return s.contains('fro') || s.contains('susp');
  }

  /// Matches that should never show scores or live badge
  bool get isNonPlayable => isPostponed || isCancelled || isFrozen;

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
    if (isPostponed) return "POSTPONED";
    if (isCancelled) return "CANCELLED";
    if (isFrozen) return "FRO";
    // Check specific finished variants BEFORE generic 'finished'
    if (s.contains('after pen') || s == 'penalties') return "FT (Pen)";
    if (s.contains('after et') || s.contains('aet')) return "FT (AET)";
    if (s.contains('finish') || s == 'ft' || s.contains('full time')) {
      return "FINISHED";
    }
    if (s.contains('sched') || s.contains('pending') || s.isEmpty) return "";
    return status.toUpperCase();
  }

  bool get isPredictionAccurate {
    // Prefer outcome_correct from CSV/Supabase when available
    if (outcomeCorrect != null && outcomeCorrect!.isNotEmpty) {
      return outcomeCorrect == '1';
    }
    // Fallback: compute from scores
    if (homeScore == null || awayScore == null || prediction == null) {
      return false;
    }
    final hs = int.tryParse(homeScore!) ?? 0;
    final as_ = int.tryParse(awayScore!) ?? 0;
    final total = hs + as_;
    final p = prediction!.toLowerCase().trim();
    final hLower = homeTeam.toLowerCase().trim();
    final aLower = awayTeam.toLowerCase().trim();

    bool teamIsHome(String t) =>
        t == hLower || hLower.startsWith(t) || t.startsWith(hLower);
    bool teamIsAway(String t) =>
        t == aLower || aLower.startsWith(t) || t.startsWith(aLower);

    // Winner & BTTS
    final bttsWinRe = RegExp(r'^(.+?)\s+to\s+win\s*&\s*btts\s+yes$');
    final bttsWinMatch = bttsWinRe.firstMatch(p);
    if (bttsWinMatch != null) {
      final team = bttsWinMatch.group(1)!.trim();
      final btts = hs > 0 && as_ > 0;
      if (teamIsHome(team)) return hs > as_ && btts;
      if (teamIsAway(team)) return as_ > hs && btts;
    }

    // 1X2
    if (p == 'home win' || p == '1') return hs > as_;
    if (p == 'away win' || p == '2') return as_ > hs;
    if (p == 'draw' || p == 'x') return hs == as_;
    if (p == 'home or away' || p == '12') return hs != as_;

    // Over/Under (standard)
    if (p.contains('over 2.5')) return total > 2;
    if (p.contains('under 2.5')) return total < 3;
    if (p.contains('over 1.5')) return total > 1;
    if (p.contains('under 1.5')) return total < 2;

    // BTTS
    if (p == 'btts yes' ||
        p == 'both teams to score' ||
        p == 'both teams to score yes') {
      return hs > 0 && as_ > 0;
    }
    if (p == 'btts no' || p == 'both teams to score no') {
      return hs == 0 || as_ == 0;
    }

    // Team to win
    if (p.endsWith(' to win')) {
      final team = p.replaceAll(' to win', '').trim();
      if (teamIsHome(team)) return hs > as_;
      if (teamIsAway(team)) return as_ > hs;
    }

    // Team or Draw
    if (p.contains(' or draw')) {
      final team = p.replaceAll(' or draw', '').trim();
      if (teamIsHome(team)) return hs >= as_;
      if (teamIsAway(team)) return as_ >= hs;
    }

    // "Home or Away" with team names (e.g., "Arsenal or Liverpool")
    final orRe = RegExp(r'^(.+?)\s+or\s+(.+?)$');
    final orMatch = orRe.firstMatch(p);
    if (orMatch != null && !p.contains('draw')) {
      final t1 = orMatch.group(1)!.trim();
      final t2 = orMatch.group(2)!.trim();
      if ((teamIsHome(t1) && teamIsAway(t2)) ||
          (teamIsAway(t1) && teamIsHome(t2))) {
        return hs != as_;
      }
    }

    // DNB
    if (p.endsWith(' (dnb)')) {
      final team =
          p.replaceAll(' to win (dnb)', '').replaceAll(' (dnb)', '').trim();
      if (hs == as_) return false; // Void shown as incorrect visually
      if (teamIsHome(team)) return hs > as_;
      if (teamIsAway(team)) return as_ > hs;
    }

    // Team Over/Under (e.g., "Arsenal Over 0.5")
    final overRe = RegExp(r'over\s+([\d.]+)');
    final overMatch = overRe.firstMatch(p);
    if (overMatch != null) {
      final threshold = double.tryParse(overMatch.group(1)!) ?? 0;
      final teamPart = p.substring(0, overMatch.start).trim();
      if (teamPart.isNotEmpty) {
        if (teamIsHome(teamPart)) return hs > threshold;
        if (teamIsAway(teamPart)) return as_ > threshold;
      }
      return total > threshold;
    }

    final underRe = RegExp(r'under\s+([\d.]+)');
    final underMatch = underRe.firstMatch(p);
    if (underMatch != null) {
      final threshold = double.tryParse(underMatch.group(1)!) ?? 0;
      final teamPart = p.substring(0, underMatch.start).trim();
      if (teamPart.isNotEmpty) {
        if (teamIsHome(teamPart)) return hs < threshold;
        if (teamIsAway(teamPart)) return as_ < threshold;
      }
      return total < threshold;
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
      liveMinute: (row['minute'] ?? row['live_minute'])?.toString(),
      isFeatured: isFeatured,
      homeCrestUrl: row['home_crest_url']?.toString(),
      awayCrestUrl: row['away_crest_url']?.toString(),
      regionFlagUrl: row['region_flag_url']?.toString(),
      leagueCrestUrl: row['league_crest_url']?.toString(),
      xgHome: xgHome,
      xgAway: xgAway,
      reasonTags: reasonTags,
      homeFormN: int.tryParse(row['home_form_n']?.toString() ?? ''),
      awayFormN: int.tryParse(row['away_form_n']?.toString() ?? ''),
      outcomeCorrect: outcomeCorrect,
    );
  }

  MatchModel mergeWith(MatchModel other) {
    return MatchModel(
      fixtureId: fixtureId,
      date: other.date.isNotEmpty ? other.date : date,
      time: other.time.isNotEmpty ? other.time : time,
      homeTeam: other.homeTeam.isNotEmpty ? other.homeTeam : homeTeam,
      awayTeam: other.awayTeam.isNotEmpty ? other.awayTeam : awayTeam,
      homeTeamId: other.homeTeamId ?? homeTeamId,
      awayTeamId: other.awayTeamId ?? awayTeamId,
      homeScore: other.homeScore ?? homeScore,
      awayScore: other.awayScore ?? awayScore,
      status: other.status,
      sport: other.sport.isNotEmpty ? other.sport : sport,
      league: other.league ?? league,
      prediction: prediction, // Preserve existing
      odds: odds, // Preserve existing
      confidence: confidence, // Preserve existing
      liveMinute: other.liveMinute ?? liveMinute,
      isFeatured: isFeatured, // Preserve existing
      valueTag: valueTag, // Preserve existing
      homeCrestUrl: other.homeCrestUrl ?? homeCrestUrl,
      awayCrestUrl: other.awayCrestUrl ?? awayCrestUrl,
      regionFlagUrl: other.regionFlagUrl ?? regionFlagUrl,
      leagueCrestUrl: other.leagueCrestUrl ?? leagueCrestUrl,
      marketReliability: marketReliability, // Preserve existing
      xgHome: xgHome, // Preserve existing
      xgAway: xgAway, // Preserve existing
      reasonTags: reasonTags, // Preserve existing
      homeFormN: homeFormN, // Preserve existing
      awayFormN: awayFormN, // Preserve existing
      outcomeCorrect: other.outcomeCorrect ?? outcomeCorrect,
    );
  }
}
