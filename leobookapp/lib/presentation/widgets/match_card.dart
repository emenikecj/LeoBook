import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:leobookapp/data/models/match_model.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/data/repositories/data_repository.dart';
import '../screens/match_details_screen.dart';
import '../screens/team_screen.dart';
import '../screens/league_screen.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:leobookapp/core/widgets/glass_container.dart';

class MatchCard extends StatelessWidget {
  final MatchModel match;
  final bool showLiveBadge;
  const MatchCard({super.key, required this.match, this.showLiveBadge = true});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final isFinished = match.status.toLowerCase().contains('finished') ||
        match.status.toUpperCase() == 'FT';

    // Parse League String "REGION: League"
    String region = "WORLD";
    String leagueName = match.league ?? "SOCCER";
    if (leagueName.contains(':')) {
      final parts = leagueName.split(':');
      if (parts.length >= 2) {
        region = parts[0].trim();
        leagueName = parts[1].trim();
      }
    }

    return GlassContainer(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      padding: const EdgeInsets.all(16),
      borderRadius: 20,
      borderColor: (match.isLive || match.isStartingSoon)
          ? AppColors.liveRed.withValues(alpha: 0.3)
          : AppColors.primary.withValues(alpha: 0.3),
      onTap: () {
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (context) => MatchDetailsScreen(match: match),
          ),
        );
      },
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              GestureDetector(
                onTap: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (context) => LeagueScreen(
                        leagueId: match.league ?? "SOCCER",
                        leagueName: match.league ?? "SOCCER",
                      ),
                    ),
                  );
                },
                child: Column(
                  children: [
                    // Region + Flag Row
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        if (match.regionFlagUrl != null &&
                            match.regionFlagUrl!.isNotEmpty)
                          CachedNetworkImage(
                            imageUrl: match.regionFlagUrl!,
                            width: 14,
                            height: 10,
                            fit: BoxFit.cover,
                            placeholder: (_, __) => Icon(
                              Icons.public,
                              size: 12,
                              color: AppColors.textGrey.withValues(alpha: 0.8),
                            ),
                            errorWidget: (_, __, ___) => Icon(
                              Icons.public,
                              size: 12,
                              color: AppColors.textGrey.withValues(alpha: 0.8),
                            ),
                          )
                        else
                          Icon(
                            Icons.public,
                            size: 12,
                            color: AppColors.textGrey.withValues(alpha: 0.8),
                          ),
                        const SizedBox(width: 6),
                        Flexible(
                          child: Text(
                            region.toUpperCase(),
                            style: TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.w900,
                              color: AppColors.textGrey.withValues(alpha: 0.8),
                              letterSpacing: 1.2,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    // League Name
                    Text(
                      leagueName.toUpperCase(),
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w900,
                        color: Colors.white, // Pop out league name
                        letterSpacing: 0.5,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 4),
                    // Date & Time
                    Text(
                      "${match.date} • ${match.time}${match.displayStatus.isEmpty ? '' : ' • ${match.displayStatus}'}",
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                        color: match.isLive
                            ? AppColors.liveRed
                            : AppColors.textGrey,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),

              // Teams Comparison / Result
              if (isFinished)
                _buildFinishedLayout(context, isDark)
              else
                _buildActiveLayout(context, isDark),

              const SizedBox(height: 12),

              // Prediction Section
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: match.isLive
                      ? AppColors.liveRed.withValues(alpha: 0.08)
                      : (isDark
                          ? Colors.white.withValues(alpha: 0.06)
                          : Colors.black.withValues(alpha: 0.04)),
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(
                    color: match.isLive
                        ? AppColors.liveRed.withValues(alpha: 0.2)
                        : (isDark
                            ? Colors.white.withValues(alpha: 0.08)
                            : Colors.black.withValues(alpha: 0.06)),
                  ),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Flexible(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            match.isLive
                                ? "IN-PLAY PREDICTION"
                                : "LEO PREDICTION",
                            style: TextStyle(
                              fontSize: 9,
                              fontWeight: FontWeight.w900,
                              color: match.isLive
                                  ? AppColors.liveRed
                                  : AppColors.textGrey,
                              letterSpacing: 0.5,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            match.prediction ?? "N/A",
                            style: TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.w900,
                              color: isFinished
                                  ? AppColors.success
                                  : AppColors.primary,
                              decoration: isFinished &&
                                      !(match.prediction
                                              ?.contains('Accurate') ??
                                          true)
                                  ? TextDecoration.lineThrough
                                  : null,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                          if (match.marketReliability != null)
                            Text(
                              "RELIABILITY: ${match.marketReliability}%",
                              style: TextStyle(
                                fontSize: 9,
                                fontWeight: FontWeight.bold,
                                color: AppColors.success.withValues(alpha: 0.7),
                              ),
                            ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 8), // Gap
                    if (match.odds != null)
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 16,
                          vertical: 8,
                        ),
                        decoration: BoxDecoration(
                          color: isFinished
                              ? Colors.white.withValues(alpha: 0.08)
                              : AppColors.primary.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(
                            color: isFinished
                                ? Colors.white.withValues(alpha: 0.1)
                                : AppColors.primary.withValues(alpha: 0.3),
                          ),
                        ),
                        child: Text(
                          match.odds!,
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w900,
                            color: isFinished
                                ? AppColors.textGrey
                                : AppColors.primary,
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ),
          if (showLiveBadge && (match.isLive || match.isStartingSoon))
            Positioned(
              top: 0,
              right: 0,
              child: _LiveBadge(
                minute: match.isLive ? match.liveMinute : "SOON",
              ),
            ),
          if (isFinished && match.isPredictionAccurate)
            Positioned(
              top: 0,
              right: 0,
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 4,
                ),
                decoration: const BoxDecoration(
                  color: AppColors.success,
                  borderRadius: BorderRadius.only(
                    topRight: Radius.circular(20),
                    bottomLeft: Radius.circular(10),
                  ),
                ),
                child: const Text(
                  "ACCURATE",
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 8,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildActiveLayout(BuildContext context, bool isDark) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Expanded(child: _buildTeamLogoCol(context, match.homeTeam, isDark)),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          child: match.isLive ||
                  (match.homeScore != null && match.awayScore != null)
              ? Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          match.homeScore ?? "0",
                          style: TextStyle(
                            fontSize: 24,
                            fontWeight: FontWeight.w900,
                            color: isDark ? Colors.white : AppColors.textDark,
                          ),
                        ),
                        const Padding(
                          padding: EdgeInsets.symmetric(horizontal: 4.0),
                          child: Text(
                            "-",
                            style: TextStyle(
                              color: AppColors.textGrey,
                              fontSize: 18,
                            ),
                          ),
                        ),
                        Text(
                          match.awayScore ?? "0",
                          style: TextStyle(
                            fontSize: 24,
                            fontWeight: FontWeight.w900,
                            color: isDark ? Colors.white : AppColors.textDark,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 2),
                    if (match.displayStatus.isNotEmpty)
                      Text(
                        match.displayStatus,
                        style: TextStyle(
                          fontSize: 8,
                          fontWeight: FontWeight.bold,
                          color: match.isLive
                              ? AppColors.liveRed
                              : AppColors.primary,
                          letterSpacing: 0.5,
                        ),
                      ),
                  ],
                )
              : const Text(
                  "VS",
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w900,
                    fontStyle: FontStyle.italic,
                    color: AppColors.textGrey,
                  ),
                ),
        ),
        Expanded(child: _buildTeamLogoCol(context, match.awayTeam, isDark)),
      ],
    );
  }

  Widget _buildFinishedLayout(BuildContext context, bool isDark) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Expanded(
          child: Column(
            children: [
              _buildFinishedRow(
                context,
                match.homeTeam,
                match.homeScore ?? "0",
                isDark,
                match.homeCrestUrl,
              ),
              const SizedBox(height: 8),
              _buildFinishedRow(
                context,
                match.awayTeam,
                match.awayScore ?? "0",
                isDark,
                match.awayCrestUrl,
              ),
            ],
          ),
        ),
        Container(
          width: 1,
          height: 40,
          margin: const EdgeInsets.only(left: 16),
          color: isDark
              ? Colors.white.withValues(alpha: 0.05)
              : Colors.black.withValues(alpha: 0.05),
        ),
        Container(
          padding: const EdgeInsets.only(left: 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              const Text(
                "RESULT",
                style: TextStyle(
                  fontSize: 9,
                  fontWeight: FontWeight.w900,
                  color: AppColors.textGrey,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                "FT",
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w900,
                  color: isDark ? Colors.white : AppColors.textDark,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                match.displayStatus,
                style: TextStyle(
                  fontSize: 8,
                  fontWeight: FontWeight.bold,
                  color: AppColors.primary,
                  letterSpacing: 0.5,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildFinishedRow(
    BuildContext context,
    String teamName,
    String score,
    bool isDark,
    String? crestUrl,
  ) {
    return GestureDetector(
      onTap: () {
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (context) => TeamScreen(
              teamName: teamName,
              repository: context.read<DataRepository>(),
            ),
          ),
        );
      },
      child: Row(
        children: [
          Container(
            width: 24,
            height: 24,
            decoration: BoxDecoration(
              color: isDark
                  ? Colors.white.withValues(alpha: 0.05)
                  : AppColors.backgroundLight,
              shape: BoxShape.circle,
            ),
            child: ClipOval(
              child: crestUrl != null && crestUrl.isNotEmpty
                  ? CachedNetworkImage(
                      imageUrl: crestUrl,
                      fit: BoxFit.contain,
                      placeholder: (context, url) => Center(
                        child: Text(
                          teamName.substring(0, 1).toUpperCase(),
                          style: const TextStyle(
                            fontSize: 8,
                            color: AppColors.textGrey,
                          ),
                        ),
                      ),
                      errorWidget: (context, url, error) => Center(
                        child: Text(
                          teamName.substring(0, 1).toUpperCase(),
                          style: const TextStyle(
                            fontSize: 8,
                            color: AppColors.textGrey,
                          ),
                        ),
                      ),
                    )
                  : Center(
                      child: Text(
                        teamName.substring(0, 1).toUpperCase(),
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                          color: AppColors.textGrey,
                        ),
                      ),
                    ),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              teamName,
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w700,
                color: isDark ? Colors.white : AppColors.textDark,
              ),
            ),
          ),
          Text(
            score,
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w900,
              color: isDark ? Colors.white : AppColors.textDark,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTeamLogoCol(BuildContext context, String teamName, bool isDark) {
    final crestUrl =
        (teamName == match.homeTeam) ? match.homeCrestUrl : match.awayCrestUrl;
    return GestureDetector(
      onTap: () {
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (context) => TeamScreen(
              teamName: teamName,
              repository: context.read<DataRepository>(),
            ),
          ),
        );
      },
      child: Column(
        children: [
          _buildTeamLogo(teamName, isDark, crestUrl),
          const SizedBox(height: 8),
          Text(
            teamName,
            textAlign: TextAlign.center,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w800,
              color: isDark ? Colors.white : AppColors.textDark,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTeamLogo(String teamName, bool isDark, String? crestUrl) {
    return Container(
      width: 56,
      height: 56,
      decoration: BoxDecoration(
        color: isDark
            ? Colors.white.withValues(alpha: 0.06)
            : Colors.black.withValues(alpha: 0.04),
        shape: BoxShape.circle,
        border: Border.all(
          color: isDark
              ? Colors.white.withValues(alpha: 0.08)
              : Colors.black.withValues(alpha: 0.06),
        ),
      ),
      child: ClipOval(
        child: crestUrl != null && crestUrl.isNotEmpty
            ? CachedNetworkImage(
                imageUrl: crestUrl,
                fit: BoxFit.contain,
                placeholder: (context, url) => Center(
                  child: Text(
                    teamName.substring(0, 1).toUpperCase(),
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w900,
                      color: AppColors.textGrey.withValues(alpha: 0.3),
                    ),
                  ),
                ),
                errorWidget: (context, url, error) => Center(
                  child: Text(
                    teamName.substring(0, 1).toUpperCase(),
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w900,
                      color: AppColors.textGrey.withValues(alpha: 0.3),
                    ),
                  ),
                ),
              )
            : Center(
                child: Text(
                  teamName.substring(0, 1).toUpperCase(),
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.w900,
                    color: AppColors.textGrey.withValues(alpha: 0.5),
                  ),
                ),
              ),
      ),
    );
  }
}

class _LiveBadge extends StatefulWidget {
  final String? minute;
  const _LiveBadge({this.minute});

  @override
  State<_LiveBadge> createState() => _LiveBadgeState();
}

class _LiveBadgeState extends State<_LiveBadge>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _animation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 1),
    )..repeat(reverse: true);
    _animation = Tween<double>(begin: 0.6, end: 1.0).animate(_controller);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _animation,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: const BoxDecoration(
          color: AppColors.liveRed,
          borderRadius: BorderRadius.only(
            topRight: Radius.circular(20),
            bottomLeft: Radius.circular(10),
          ),
        ),
        child: Text(
          "LIVE ${widget.minute ?? ''}".toUpperCase(),
          style: const TextStyle(
            color: Colors.white,
            fontSize: 8,
            fontWeight: FontWeight.w900,
          ),
        ),
      ),
    );
  }
}
