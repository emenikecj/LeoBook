// accuracy_report_card.dart: Data-driven accuracy report computed from predictions.
// Part of LeoBook App — Responsive Widgets
//
// Classes: AccuracyReportCard, _LeagueAccuracyGrid, _SectionHeader, _LeagueAccuracy

import 'package:flutter/material.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/responsive_constants.dart';
import '../../../data/models/match_model.dart';

class AccuracyReportCard extends StatefulWidget {
  final List<MatchModel> matches;

  const AccuracyReportCard({super.key, required this.matches});

  @override
  State<AccuracyReportCard> createState() => _AccuracyReportCardState();
}

class _AccuracyReportCardState extends State<AccuracyReportCard> {
  bool _isExpanded = false;

  @override
  Widget build(BuildContext context) {
    final isDesktop = Responsive.isDesktop(context);

    // Compute accuracy from finished matches with predictions
    final finished = widget.matches
        .where((m) =>
            m.isFinished && m.prediction != null && m.prediction!.isNotEmpty)
        .toList();

    final accurate = finished.where((m) => m.isPredictionAccurate).length;
    final totalAccuracy =
        finished.isNotEmpty ? (accurate / finished.length * 100).round() : 0;

    // Compute per-league accuracy (ALL leagues, sorted by accuracy desc)
    final allLeagueStats = _computeLeagueAccuracy(finished);
    final topLeagues = allLeagueStats.take(3).toList();

    // Performance label
    String perfLabel = "AWAITING DATA";
    Color perfColor = AppColors.textGrey;
    IconData trendIcon = Icons.remove_rounded;

    if (finished.isNotEmpty) {
      if (totalAccuracy >= 80) {
        perfLabel = "HIGH PERFORMANCE";
        perfColor = AppColors.successGreen;
        trendIcon = Icons.trending_up_rounded;
      } else if (totalAccuracy >= 60) {
        perfLabel = "AVERAGE";
        perfColor = AppColors.warning;
        trendIcon = Icons.trending_flat_rounded;
      } else {
        perfLabel = "NEEDS IMPROVEMENT";
        perfColor = AppColors.liveRed;
        trendIcon = Icons.trending_down_rounded;
      }
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            _SectionHeader(
              title: "ACCURACY REPORT",
              icon: Icons.check_circle_rounded,
              color: AppColors.successGreen,
            ),
            Text(
              "${finished.length} MATCHES ANALYZED",
              style: TextStyle(
                fontSize: Responsive.sp(context, 7),
                fontWeight: FontWeight.w900,
                color: AppColors.textGrey,
                letterSpacing: 1.5,
              ),
            ),
          ],
        ),
        SizedBox(height: Responsive.sp(context, 10)),
        Container(
          padding: EdgeInsets.all(Responsive.sp(context, 12)),
          decoration: BoxDecoration(
            color: AppColors.desktopSearchFill.withValues(alpha: 0.5),
            borderRadius: BorderRadius.circular(Responsive.sp(context, 14)),
            border: Border.all(color: Colors.white.withValues(alpha: 0.05)),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (isDesktop)
                Padding(
                  padding:
                      EdgeInsets.symmetric(vertical: Responsive.sp(context, 8)),
                  child: Row(
                    children: [
                      _buildMainAccuracy(context, totalAccuracy, perfLabel,
                          perfColor, trendIcon, finished.length),
                      SizedBox(width: Responsive.sp(context, 24)),
                      // Dynamic vertical separator
                      Container(
                        width: 1,
                        height: Responsive.sp(context, 60),
                        color: Colors.white.withValues(alpha: 0.1),
                      ),
                      SizedBox(width: Responsive.sp(context, 24)),
                      Expanded(child: _LeagueAccuracyGrid(leagues: topLeagues)),
                    ],
                  ),
                )
              else
                Column(
                  children: [
                    _buildMainAccuracy(context, totalAccuracy, perfLabel,
                        perfColor, trendIcon, finished.length),
                    SizedBox(height: Responsive.sp(context, 12)),
                    _LeagueAccuracyGrid(leagues: topLeagues),
                  ],
                ),

              // Expandable league list
              if (allLeagueStats.length > 3) ...[
                SizedBox(height: Responsive.sp(context, 8)),
                GestureDetector(
                  onTap: () => setState(() => _isExpanded = !_isExpanded),
                  child: Container(
                    padding: EdgeInsets.symmetric(
                      vertical: Responsive.sp(context, 6),
                      horizontal: Responsive.sp(context, 10),
                    ),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.03),
                      borderRadius:
                          BorderRadius.circular(Responsive.sp(context, 8)),
                      border: Border.all(
                          color: Colors.white.withValues(alpha: 0.06)),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          _isExpanded
                              ? "HIDE ALL LEAGUES"
                              : "VIEW ALL ${allLeagueStats.length} LEAGUES",
                          style: TextStyle(
                            fontSize: Responsive.sp(context, 7),
                            fontWeight: FontWeight.w900,
                            color: AppColors.primary,
                            letterSpacing: 1.2,
                          ),
                        ),
                        SizedBox(width: Responsive.sp(context, 4)),
                        Icon(
                          _isExpanded
                              ? Icons.keyboard_arrow_up_rounded
                              : Icons.keyboard_arrow_down_rounded,
                          color: AppColors.primary,
                          size: Responsive.sp(context, 14),
                        ),
                      ],
                    ),
                  ),
                ),
                if (_isExpanded) ...[
                  SizedBox(height: Responsive.sp(context, 8)),
                  _ExpandedLeagueList(leagues: allLeagueStats),
                ],
              ],
            ],
          ),
        ),
      ],
    );
  }

  List<_LeagueAccData> _computeLeagueAccuracy(List<MatchModel> finished) {
    final Map<String, List<MatchModel>> byLeague = {};
    for (var m in finished) {
      final leagueKey = m.league ?? 'Unknown';
      byLeague.putIfAbsent(leagueKey, () => []).add(m);
    }

    // Sort: accuracy DESC → match count DESC (highest accuracy + volume first)
    final sorted = byLeague.entries.toList()
      ..sort((a, b) {
        final accA = a.value.where((m) => m.isPredictionAccurate).length /
            (a.value.isEmpty ? 1 : a.value.length);
        final accB = b.value.where((m) => m.isPredictionAccurate).length /
            (b.value.isEmpty ? 1 : b.value.length);

        // Primary: accuracy descending
        final accCmp = accB.compareTo(accA);
        if (accCmp != 0) return accCmp;

        // Secondary: match count descending
        return b.value.length.compareTo(a.value.length);
      });

    final colors = [
      AppColors.primary,
      AppColors.warning,
      AppColors.successGreen,
      const Color(0xFF8B5CF6), // purple
      const Color(0xFFEC4899), // pink
      const Color(0xFF06B6D4), // cyan
      const Color(0xFFF97316), // orange
      const Color(0xFF10B981), // emerald
    ];

    return sorted.asMap().entries.map((entry) {
      final i = entry.key;
      final e = entry.value;
      final acc = e.value.where((m) => m.isPredictionAccurate).length;
      final pct = e.value.isNotEmpty ? acc / e.value.length : 0.0;

      // Extract region and league name
      String rawName = e.key;
      String region = "";
      String leagueName = rawName;

      if (rawName.contains(':')) {
        final parts = rawName.split(':');
        region = parts.first.trim();
        leagueName = parts.last.trim();
      } else if (rawName.contains('-')) {
        final parts = rawName.split('-');
        region = parts.first.trim();
        leagueName = parts.sublist(1).join('-').trim();
      }

      // Grab first available crest url for this league
      String? crestUrl;
      for (var match in e.value) {
        if (match.leagueCrestUrl != null && match.leagueCrestUrl!.isNotEmpty) {
          crestUrl = match.leagueCrestUrl;
          break;
        }
      }

      return _LeagueAccData(
        region: region,
        league: leagueName,
        percentage: pct,
        color: colors[i % colors.length],
        matchCount: e.value.length,
        crestUrl: crestUrl,
      );
    }).toList();
  }

  Widget _buildMainAccuracy(BuildContext context, int totalAccuracy,
      String perfLabel, Color perfColor, IconData trendIcon, int matchCount) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Text(
          "TOTAL ACCURACY",
          style: TextStyle(
            fontSize: Responsive.sp(context, 7),
            fontWeight: FontWeight.w900,
            color: AppColors.textGrey,
            letterSpacing: 1.5,
          ),
        ),
        Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text(
              "$totalAccuracy",
              style: TextStyle(
                fontSize: Responsive.sp(context, 32),
                fontWeight: FontWeight.w900,
                color: Colors.white,
                fontStyle: FontStyle.italic,
                height: 1.0,
                letterSpacing: -1,
              ),
            ),
            Padding(
              padding: EdgeInsets.only(bottom: Responsive.sp(context, 4)),
              child: Text(
                "%",
                style: TextStyle(
                  fontSize: Responsive.sp(context, 14),
                  fontWeight: FontWeight.w700,
                  color: perfColor,
                ),
              ),
            ),
            SizedBox(width: Responsive.sp(context, 4)),
            Padding(
              padding: EdgeInsets.only(bottom: Responsive.sp(context, 4)),
              child: Icon(
                trendIcon,
                color: perfColor,
                size: Responsive.sp(context, 20),
              ),
            ),
          ],
        ),
        SizedBox(height: Responsive.sp(context, 2)),
        Text(
          "$matchCount MATCHES",
          style: TextStyle(
            fontSize: Responsive.sp(context, 6),
            fontWeight: FontWeight.w700,
            color: AppColors.textGrey.withValues(alpha: 0.7),
            letterSpacing: 1.0,
          ),
        ),
        SizedBox(height: Responsive.sp(context, 4)),
        Container(
          padding: EdgeInsets.symmetric(
            horizontal: Responsive.sp(context, 6),
            vertical: Responsive.sp(context, 3),
          ),
          decoration: BoxDecoration(
            color: perfColor.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(Responsive.sp(context, 4)),
          ),
          child: Text(
            perfLabel,
            style: TextStyle(
              fontSize: Responsive.sp(context, 6),
              fontWeight: FontWeight.w900,
              color: perfColor,
              letterSpacing: 1,
            ),
          ),
        ),
      ],
    );
  }
}

class _LeagueAccData {
  final String region;
  final String league;
  final double percentage;
  final Color color;
  final int matchCount;
  final String? crestUrl;

  const _LeagueAccData({
    required this.region,
    required this.league,
    required this.percentage,
    required this.color,
    required this.matchCount,
    this.crestUrl,
  });
}

class _ExpandedLeagueList extends StatelessWidget {
  final List<_LeagueAccData> leagues;
  const _ExpandedLeagueList({required this.leagues});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: leagues.map((l) {
        final pctInt = (l.percentage * 100).toInt();
        return Padding(
          padding: EdgeInsets.only(bottom: Responsive.sp(context, 4)),
          child: Container(
            padding: EdgeInsets.symmetric(
              horizontal: Responsive.sp(context, 10),
              vertical: Responsive.sp(context, 6),
            ),
            decoration: BoxDecoration(
              color: AppColors.desktopHeaderBg,
              borderRadius: BorderRadius.circular(Responsive.sp(context, 8)),
              border: Border.all(color: Colors.white.withValues(alpha: 0.04)),
            ),
            child: Row(
              children: [
                Container(
                  width: Responsive.sp(context, 3),
                  height: Responsive.sp(context, 24),
                  decoration: BoxDecoration(
                    color: l.color,
                    borderRadius:
                        BorderRadius.circular(Responsive.sp(context, 2)),
                  ),
                ),
                SizedBox(width: Responsive.sp(context, 8)),
                // Crest
                Container(
                  width: Responsive.sp(context, 24),
                  height: Responsive.sp(context, 24),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.05),
                    shape: BoxShape.circle,
                  ),
                  clipBehavior: Clip.antiAlias,
                  child: l.crestUrl != null && l.crestUrl!.isNotEmpty
                      ? CachedNetworkImage(
                          imageUrl: l.crestUrl!,
                          fit: BoxFit.cover,
                          errorWidget: (context, url, error) =>
                              _buildInitials(l.league, context),
                        )
                      : _buildInitials(l.league, context),
                ),
                SizedBox(width: Responsive.sp(context, 10)),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (l.region.isNotEmpty)
                        Text(
                          l.region.toUpperCase(),
                          style: TextStyle(
                            fontSize: Responsive.sp(context, 6),
                            fontWeight: FontWeight.w600,
                            color: AppColors.textGrey,
                            letterSpacing: 1.0,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      Text(
                        l.league.length > 30
                            ? l.league.substring(0, 30).toUpperCase()
                            : l.league.toUpperCase(),
                        style: TextStyle(
                          fontSize: Responsive.sp(context, 7),
                          fontWeight: FontWeight.w800,
                          color: Colors.white.withValues(alpha: 0.9),
                          letterSpacing: 0.5,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      SizedBox(height: Responsive.sp(context, 2)),
                      ClipRRect(
                        borderRadius:
                            BorderRadius.circular(Responsive.sp(context, 2)),
                        child: LinearProgressIndicator(
                          value: l.percentage.clamp(0.0, 1.0),
                          backgroundColor: Colors.white.withValues(alpha: 0.05),
                          color: l.color,
                          minHeight: Responsive.sp(context, 2),
                        ),
                      ),
                    ],
                  ),
                ),
                SizedBox(width: Responsive.sp(context, 10)),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      "$pctInt%",
                      style: TextStyle(
                        fontSize: Responsive.sp(context, 12),
                        fontWeight: FontWeight.w900,
                        color: Colors.white,
                        fontStyle: FontStyle.italic,
                      ),
                    ),
                    Text(
                      "${l.matchCount} ${l.matchCount == 1 ? 'match' : 'matches'}",
                      style: TextStyle(
                        fontSize: Responsive.sp(context, 6),
                        fontWeight: FontWeight.w600,
                        color: AppColors.textGrey,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        );
      }).toList(),
    );
  }

  Widget _buildInitials(String name, BuildContext context) {
    String initials = "L";
    if (name.isNotEmpty) {
      initials = name.substring(0, 1).toUpperCase();
    }
    return Center(
      child: Text(
        initials,
        style: TextStyle(
          color: Colors.white.withValues(alpha: 0.5),
          fontWeight: FontWeight.bold,
          fontSize: Responsive.sp(context, 10),
        ),
      ),
    );
  }
}

class _LeagueAccuracyGrid extends StatelessWidget {
  final List<_LeagueAccData> leagues;
  const _LeagueAccuracyGrid({required this.leagues});

  @override
  Widget build(BuildContext context) {
    if (leagues.isEmpty) {
      return Center(
        child: Text(
          "NO LEAGUE DATA YET",
          style: TextStyle(
            fontSize: Responsive.sp(context, 7),
            color: AppColors.textGrey,
            fontWeight: FontWeight.w900,
          ),
        ),
      );
    }

    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: leagues
          .map((l) => Expanded(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  child: _LeagueAccuracy(
                    region: l.region,
                    league: l.league.length > 12
                        ? l.league.substring(0, 12).toUpperCase()
                        : l.league.toUpperCase(),
                    percentage: l.percentage,
                    color: l.color,
                    matchCount: l.matchCount,
                    crestUrl: l.crestUrl,
                  ),
                ),
              ))
          .toList(),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final String title;
  final IconData icon;
  final Color color;

  const _SectionHeader({
    required this.title,
    required this.icon,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, color: color, size: Responsive.sp(context, 12)),
        SizedBox(width: Responsive.sp(context, 6)),
        Text(
          title,
          style: TextStyle(
            fontSize: Responsive.sp(context, 9),
            fontWeight: FontWeight.w900,
            letterSpacing: 1.5,
            color: Colors.white,
          ),
        ),
      ],
    );
  }
}

class _LeagueAccuracy extends StatelessWidget {
  final String region;
  final String league;
  final double percentage;
  final Color color;
  final int matchCount;
  final String? crestUrl;

  const _LeagueAccuracy({
    required this.region,
    required this.league,
    required this.percentage,
    required this.color,
    required this.matchCount,
    this.crestUrl,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.all(Responsive.sp(context, 8)),
      decoration: BoxDecoration(
        color: AppColors.desktopHeaderBg,
        borderRadius: BorderRadius.circular(Responsive.sp(context, 10)),
        border: Border.all(color: Colors.white.withValues(alpha: 0.05)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Flexible(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (region.isNotEmpty)
                      Text(
                        region.toUpperCase(),
                        style: TextStyle(
                          fontSize: Responsive.sp(context, 5),
                          fontWeight: FontWeight.w600,
                          color: AppColors.textGrey,
                          letterSpacing: 1.0,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    Text(
                      league,
                      style: TextStyle(
                        fontSize: Responsive.sp(context, 6),
                        fontWeight: FontWeight.w900,
                        color: Colors.white,
                        letterSpacing: 1.0,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
              if (crestUrl != null && crestUrl!.isNotEmpty)
                Container(
                  width: Responsive.sp(context, 14),
                  height: Responsive.sp(context, 14),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.1),
                    shape: BoxShape.circle,
                  ),
                  clipBehavior: Clip.antiAlias,
                  child: CachedNetworkImage(
                    imageUrl: crestUrl!,
                    fit: BoxFit.cover,
                    errorWidget: (context, url, error) => Icon(
                      Icons.sports_soccer_rounded,
                      color: color.withValues(alpha: 0.5),
                      size: Responsive.sp(context, 10),
                    ),
                  ),
                )
              else
                Icon(
                  Icons.sports_soccer_rounded,
                  color: color.withValues(alpha: 0.5),
                  size: Responsive.sp(context, 12),
                ),
            ],
          ),
          SizedBox(height: Responsive.sp(context, 4)),
          Text(
            "${(percentage * 100).toInt()}%",
            style: TextStyle(
              fontSize: Responsive.sp(context, 16),
              fontWeight: FontWeight.w900,
              color: Colors.white,
              fontStyle: FontStyle.italic,
              letterSpacing: -0.5,
            ),
          ),
          Text(
            "$matchCount ${matchCount == 1 ? 'match' : 'matches'}",
            style: TextStyle(
              fontSize: Responsive.sp(context, 5),
              fontWeight: FontWeight.w600,
              color: AppColors.textGrey.withValues(alpha: 0.7),
            ),
          ),
          SizedBox(height: Responsive.sp(context, 4)),
          Container(
            height: Responsive.sp(context, 2),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.05),
              borderRadius: BorderRadius.circular(10),
            ),
            child: FractionallySizedBox(
              alignment: Alignment.centerLeft,
              widthFactor: percentage.clamp(0.0, 1.0),
              child: Container(
                decoration: BoxDecoration(
                  color: color,
                  borderRadius: BorderRadius.circular(10),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
