// news_feed.dart: news_feed.dart: Widget/screen for App — Widgets.
// Part of LeoBook App — Widgets
//
// Classes: NewsFeed, _NewsCard, _NewsCardState

import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/core/constants/responsive_constants.dart';
import 'package:leobookapp/data/models/news_model.dart';

class NewsFeed extends StatelessWidget {
  final List<NewsModel> news;

  const NewsFeed({super.key, required this.news});

  @override
  Widget build(BuildContext context) {
    if (news.isEmpty) return const SizedBox.shrink();
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final w = MediaQuery.sizeOf(context).width;
    final cardW = Responsive.cardWidth(w, minWidth: 160, maxWidth: 260);
    final listH = cardW * 0.85;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: EdgeInsets.symmetric(
            horizontal: Responsive.sp(context, 10),
            vertical: Responsive.sp(context, 6),
          ),
          child: Row(
            children: [
              Icon(Icons.newspaper,
                  color: AppColors.primary, size: Responsive.sp(context, 14)),
              SizedBox(width: Responsive.sp(context, 5)),
              Text(
                "LATEST UPDATES",
                style: TextStyle(
                  fontSize: Responsive.sp(context, 9),
                  fontWeight: FontWeight.w700,
                  letterSpacing: 0.8,
                  color: isDark
                      ? Colors.white.withValues(alpha: 0.7)
                      : AppColors.textDark,
                ),
              ),
            ],
          ),
        ),
        SizedBox(
          height: listH,
          child: ListView.builder(
            scrollDirection: Axis.horizontal,
            padding:
                EdgeInsets.symmetric(horizontal: Responsive.sp(context, 10)),
            itemCount: news.length,
            itemBuilder: (context, index) {
              return _NewsCard(
                item: news[index],
                isDark: isDark,
                cardWidth: cardW,
              );
            },
          ),
        ),
      ],
    );
  }
}

class _NewsCard extends StatefulWidget {
  final NewsModel item;
  final bool isDark;
  final double cardWidth;

  const _NewsCard({
    required this.item,
    required this.isDark,
    required this.cardWidth,
  });

  @override
  State<_NewsCard> createState() => _NewsCardState();
}

class _NewsCardState extends State<_NewsCard> {
  bool _isHovered = false;

  @override
  Widget build(BuildContext context) {
    final item = widget.item;
    final isDark = widget.isDark;
    final cardWidth = widget.cardWidth;

    return MouseRegion(
      onEnter: (_) => setState(() => _isHovered = true),
      onExit: (_) => setState(() => _isHovered = false),
      child: AnimatedScale(
        scale: _isHovered ? 1.02 : 1.0,
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOutCubic,
        child: GestureDetector(
          onTap: () async {
            final uri = Uri.parse(item.url);
            if (await canLaunchUrl(uri)) {
              await launchUrl(uri);
            }
          },
          child: Container(
            width: cardWidth,
            margin: EdgeInsets.only(right: Responsive.sp(context, 8)),
            decoration: BoxDecoration(
              color: isDark
                  ? (_isHovered
                      ? Colors.white.withValues(alpha: 0.08)
                      : Colors.white.withValues(alpha: 0.06))
                  : (_isHovered
                      ? Colors.white
                      : Colors.white.withValues(alpha: 0.85)),
              borderRadius: BorderRadius.circular(Responsive.sp(context, 12)),
              border: Border.all(
                color: _isHovered
                    ? AppColors.primary.withValues(alpha: 0.5)
                    : (isDark
                        ? Colors.white.withValues(alpha: 0.08)
                        : Colors.black.withValues(alpha: 0.06)),
                width: 0.5,
              ),
              boxShadow: _isHovered
                  ? [
                      BoxShadow(
                        color: AppColors.primary.withValues(alpha: 0.15),
                        blurRadius: 12,
                        spreadRadius: 2,
                      )
                    ]
                  : null,
            ),
            clipBehavior: Clip.antiAlias,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                AspectRatio(
                  aspectRatio: 16 / 9,
                  child: Container(
                    color: isDark
                        ? Colors.white.withValues(alpha: 0.04)
                        : Colors.black.withValues(alpha: 0.04),
                    child: Icon(
                      Icons.image_outlined,
                      color: isDark ? Colors.white12 : Colors.black12,
                      size: Responsive.sp(context, 22),
                    ),
                  ),
                ),
                Expanded(
                  child: Padding(
                    padding: EdgeInsets.all(Responsive.sp(context, 8)),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          child: Text(
                            item.title,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              fontSize: Responsive.sp(context, 9),
                              fontWeight: FontWeight.w700,
                              height: 1.3,
                              color: isDark ? Colors.white : AppColors.textDark,
                            ),
                          ),
                        ),
                        SizedBox(height: Responsive.sp(context, 4)),
                        Row(
                          children: [
                            Text(
                              item.source.toUpperCase(),
                              style: TextStyle(
                                fontSize: Responsive.sp(context, 7),
                                fontWeight: FontWeight.w700,
                                color: AppColors.primary,
                                letterSpacing: 0.3,
                              ),
                            ),
                            const Spacer(),
                            Icon(
                              Icons.access_time_filled,
                              size: Responsive.sp(context, 7),
                              color: AppColors.textGrey.withValues(alpha: 0.5),
                            ),
                            SizedBox(width: Responsive.sp(context, 2)),
                            Text(
                              item.timeAgo.toUpperCase(),
                              style: TextStyle(
                                fontSize: Responsive.sp(context, 7),
                                fontWeight: FontWeight.w600,
                                color:
                                    AppColors.textGrey.withValues(alpha: 0.5),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
