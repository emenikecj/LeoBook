import 'package:leobookapp/data/models/match_model.dart';

enum MatchTabType { all, live, finished, scheduled }

class MatchSorter {
  static List<dynamic> getSortedMatches(
    List<MatchModel> matches,
    MatchTabType type,
  ) {
    switch (type) {
      case MatchTabType.all:
        return _groupByLeague(matches);
      case MatchTabType.live:
        return _groupByLeague(_filterLiveMatches(matches));
      case MatchTabType.finished:
        return _groupByTime(_filterFinishedMatches(matches), descending: true);
      case MatchTabType.scheduled:
        return _groupByTime(_filterScheduledMatches(matches),
            descending: false);
    }
  }

  static List<dynamic> _groupByLeague(List<MatchModel> matches) {
    if (matches.isEmpty) return [];

    final Map<String, List<MatchModel>> groups = {};
    for (var match in matches) {
      final key = match.league?.trim() ?? "Other";
      if (!groups.containsKey(key)) {
        groups[key] = [];
      }
      groups[key]!.add(match);
    }

    final sortedKeys = groups.keys.toList()..sort();

    final List<dynamic> result = [];
    for (var key in sortedKeys) {
      final groupMatches = groups[key]!;
      groupMatches.sort((a, b) {
        int timeComp = a.time.compareTo(b.time);
        if (timeComp != 0) return timeComp;
        return a.homeTeam.compareTo(b.homeTeam);
      });

      result.add(MatchGroupHeader(title: key));
      result.addAll(groupMatches);
    }
    return result;
  }

  static List<dynamic> _groupByTime(List<MatchModel> matches,
      {required bool descending}) {
    if (matches.isEmpty) return [];

    // Group by Hour (HH:00)
    final Map<String, List<MatchModel>> groups = {};
    for (var match in matches) {
      // Assuming match.time is "HH:mm"
      final hour = match.time.split(':')[0];
      final key = "$hour:00";
      if (!groups.containsKey(key)) {
        groups[key] = [];
      }
      groups[key]!.add(match);
    }

    final sortedKeys = groups.keys.toList();
    if (descending) {
      sortedKeys.sort((a, b) => b.compareTo(a));
    } else {
      sortedKeys.sort((a, b) => a.compareTo(b));
    }

    final List<dynamic> result = [];
    for (var key in sortedKeys) {
      final groupMatches = groups[key]!;
      groupMatches.sort((a, b) {
        if (descending) {
          int timeComp = b.time.compareTo(a.time);
          if (timeComp != 0) return timeComp;
          return a.homeTeam.compareTo(b.homeTeam);
        } else {
          int timeComp = a.time.compareTo(b.time);
          if (timeComp != 0) return timeComp;
          return a.homeTeam.compareTo(b.homeTeam);
        }
      });

      result.add(MatchGroupHeader(title: key));
      result.addAll(groupMatches);
    }
    return result;
  }

  /// LIVE: currentTime >= matchTime AND currentTime < matchTime + 2.5hrs
  static List<MatchModel> _filterLiveMatches(List<MatchModel> matches) {
    return matches.where((m) => m.isLive).toList();
  }

  /// FINISHED: status says finished OR currentTime > matchTime + 2.5hrs
  static List<MatchModel> _filterFinishedMatches(List<MatchModel> matches) {
    return matches.where((m) => m.isFinished).toList();
  }

  /// SCHEDULED: not live AND not finished → currentTime < matchTime
  static List<MatchModel> _filterScheduledMatches(List<MatchModel> matches) {
    return matches.where((m) => !m.isLive && !m.isFinished).toList();
  }
}

class MatchGroupHeader {
  final String title;
  MatchGroupHeader({required this.title});
}
