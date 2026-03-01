// desktop_home_content.dart: desktop_home_content.dart: Widget/screen for App — Responsive Widgets.
// Part of LeoBook App — Responsive Widgets
//
// Classes: DesktopHomeContent, _DesktopHomeContentState, _PinnedHeaderDelegate

import 'dart:ui';
import 'package:flutter/material.dart';
import '../shared/category_bar.dart';
import '../shared/featured_carousel.dart';
import '../shared/accuracy_report_card.dart';
import '../../../logic/cubit/home_cubit.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/responsive_constants.dart';
import '../../../core/utils/match_sorter.dart';
import 'package:leobookapp/presentation/widgets/shared/match_card.dart';
import 'package:leobookapp/data/models/match_model.dart';
import '../../../core/theme/liquid_glass_theme.dart';
import '../shared/footnote_section.dart';

class DesktopHomeContent extends StatefulWidget {
  final HomeLoaded state;
  final VoidCallback? onViewAllPredictions;

  const DesktopHomeContent({
    super.key,
    required this.state,
    this.onViewAllPredictions,
  });

  @override
  State<DesktopHomeContent> createState() => _DesktopHomeContentState();
}

class _DesktopHomeContentState extends State<DesktopHomeContent>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  late ScrollController _scrollController;
  final GlobalKey _tabBarKey = GlobalKey();
  final Map<String, GlobalKey> _sectionKeys = {};
  int _visibleMatchCount = 12;

  int _allCount = 0;
  int _liveCount = 0;
  int _finishedCount = 0;
  int _scheduledCount = 0;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
    _tabController.addListener(_handleTabChange);
    _scrollController = ScrollController();
    _computeCounts();
  }

  @override
  void didUpdateWidget(covariant DesktopHomeContent oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.state != widget.state) {
      _computeCounts();
    }
  }

  void _computeCounts() {
    final matches = widget.state.filteredMatches.cast<MatchModel>();
    _allCount = matches.length;
    _liveCount = MatchSorter.getSortedMatches(matches, MatchTabType.live)
        .whereType<MatchModel>()
        .length;
    _finishedCount =
        MatchSorter.getSortedMatches(matches, MatchTabType.finished)
            .whereType<MatchModel>()
            .length;
    _scheduledCount =
        MatchSorter.getSortedMatches(matches, MatchTabType.scheduled)
            .whereType<MatchModel>()
            .length;
  }

  void _handleTabChange() {
    if (_tabController.indexIsChanging) {
      if (_visibleMatchCount != 12) {
        setState(() => _visibleMatchCount = 12);
      } else {
        setState(() {});
      }
    }
  }

  @override
  void dispose() {
    _tabController.removeListener(_handleTabChange);
    _tabController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final hPad = Responsive.horizontalPadding(context);

    return Stack(
      children: [
        CustomScrollView(
          controller: _scrollController,
          slivers: [
            SliverPersistentHeader(
              pinned: true,
              delegate: _PinnedHeaderDelegate(
                height: Responsive.dp(context, 56),
                child: Container(
                  color: Theme.of(context).scaffoldBackgroundColor,
                  padding: EdgeInsets.symmetric(horizontal: hPad),
                  alignment: Alignment.centerLeft,
                  child: const CategoryBar(),
                ),
              ),
            ),
            SliverPadding(
              padding: EdgeInsets.fromLTRB(
                  hPad, 0, hPad, Responsive.dp(context, 20)),
              sliver: SliverList(
                delegate: SliverChildListDelegate([
                  FeaturedCarousel(
                    matches: widget.state.featuredMatches,
                    recommendations: widget.state.filteredRecommendations,
                    allMatches: widget.state.allMatches,
                    onViewAll: widget.onViewAllPredictions,
                  ),
                  SizedBox(height: Responsive.dp(context, 24)),
                  AccuracyReportCard(matches: widget.state.allMatches),
                  SizedBox(height: Responsive.dp(context, 24)),
                ]),
              ),
            ),
            SliverPersistentHeader(
              pinned: true,
              delegate: _PinnedHeaderDelegate(
                height: Responsive.dp(context, 36),
                child: Container(
                  key: _tabBarKey,
                  color: Theme.of(context).scaffoldBackgroundColor,
                  padding: EdgeInsets.symmetric(horizontal: hPad),
                  alignment: Alignment.centerLeft,
                  child: _buildTabBar(),
                ),
              ),
            ),
            SliverPadding(
              padding: EdgeInsets.only(
                left: hPad,
                right: hPad,
                top: Responsive.dp(context, 14),
                bottom: Responsive.dp(context, 14),
              ),
              sliver: Builder(
                builder: (context) {
                  final index = _tabController.index;
                  MatchTabType type;
                  switch (index) {
                    case 1:
                      type = MatchTabType.live;
                      break;
                    case 2:
                      type = MatchTabType.finished;
                      break;
                    case 3:
                      type = MatchTabType.scheduled;
                      break;
                    default:
                      type = MatchTabType.all;
                  }

                  final items = MatchSorter.getSortedMatches(
                    widget.state.filteredMatches.cast(),
                    type,
                  );

                  if (items.isEmpty) {
                    return SliverToBoxAdapter(
                      child: Center(
                        child: Text(
                          "No matches found for this category",
                          style: TextStyle(
                            color: AppColors.textGrey,
                            fontSize: Responsive.dp(context, 10),
                          ),
                        ),
                      ),
                    );
                  }

                  final List<Widget> sliverItems = [];
                  List<MatchModel> currentGroupMatches = [];

                  void flushGroup() {
                    if (currentGroupMatches.isNotEmpty) {
                      final groupSnapshot =
                          List<MatchModel>.from(currentGroupMatches);
                      sliverItems.add(
                        LayoutBuilder(
                          builder: (context, constraints) {
                            const crossAxisCount = 3;
                            final spacing = Responsive.dp(context, 12);
                            final itemWidth = (constraints.maxWidth -
                                    (spacing * (crossAxisCount - 1))) /
                                crossAxisCount;

                            return Wrap(
                              spacing: spacing,
                              runSpacing: spacing,
                              children: groupSnapshot
                                  .map(
                                    (m) => SizedBox(
                                      width: itemWidth,
                                      child: MatchCard(
                                        match: m,
                                        showLeagueHeader:
                                            type != MatchTabType.all,
                                      ),
                                    ),
                                  )
                                  .toList(),
                            );
                          },
                        ),
                      );
                      sliverItems
                          .add(SizedBox(height: Responsive.dp(context, 18)));
                      currentGroupMatches = [];
                    }
                  }

                  for (final item in items) {
                    if (item is MatchGroupHeader) {
                      flushGroup();
                      final key = _sectionKeys.putIfAbsent(
                          item.title, () => GlobalKey());
                      sliverItems.add(_buildSectionHeader(item.title, key));
                    } else if (item is MatchModel) {
                      currentGroupMatches.add(item);
                    }
                  }
                  flushGroup();

                  return SliverList(
                    delegate: SliverChildBuilderDelegate(
                      (context, i) => sliverItems[i],
                      childCount: sliverItems.length,
                    ),
                  );
                },
              ),
            ),
            const SliverToBoxAdapter(
              child: FootnoteSection(),
            ),
          ],
        ),
      ],
    );
  }

  TabBar _buildTabBar() {
    return TabBar(
      controller: _tabController,
      isScrollable: true,
      labelPadding: EdgeInsets.only(right: Responsive.dp(context, 20)),
      indicatorColor: AppColors.primary,
      indicatorWeight: 2,
      dividerColor: Colors.white10,
      labelColor: Colors.white,
      unselectedLabelColor: AppColors.textGrey,
      labelStyle: TextStyle(
        fontSize: Responsive.dp(context, 10),
        fontWeight: FontWeight.w900,
        letterSpacing: 1.2,
      ),
      tabs: [
        Tab(text: "ALL PREDICTIONS ($_allCount)"),
        Tab(text: "LIVE ($_liveCount)"),
        Tab(text: "FINISHED ($_finishedCount)"),
        Tab(text: "SCHEDULED ($_scheduledCount)"),
      ],
    );
  }

  Widget _buildSectionHeader(String title, Key? key) {
    return Padding(
      key: key,
      padding: EdgeInsets.only(
        bottom: Responsive.dp(context, 10),
        top: Responsive.dp(context, 14),
      ),
      child: Row(
        children: [
          Container(
            width: Responsive.dp(context, 2.5),
            height: Responsive.dp(context, 10),
            decoration: BoxDecoration(
              color: AppColors.primary,
              borderRadius: BorderRadius.circular(1),
            ),
          ),
          SizedBox(width: Responsive.dp(context, 5)),
          Text(
            title.toUpperCase(),
            style: TextStyle(
              color: Colors.white,
              fontSize: Responsive.dp(context, 10),
              fontWeight: FontWeight.bold,
              letterSpacing: 1.0,
            ),
          ),
          SizedBox(width: Responsive.dp(context, 10)),
          Expanded(
            child: Container(
              height: 0.5,
              color: Colors.white10,
            ),
          ),
        ],
      ),
    );
  }
}

class _PinnedHeaderDelegate extends SliverPersistentHeaderDelegate {
  final Widget child;
  final double height;

  _PinnedHeaderDelegate({required this.child, required this.height});

  @override
  double get minExtent => height;

  @override
  double get maxExtent => height;

  @override
  Widget build(
    BuildContext context,
    double shrinkOffset,
    bool overlapsContent,
  ) {
    return ClipRect(
      child: BackdropFilter(
        filter: ImageFilter.blur(
          sigmaX: LiquidGlassTheme.blurRadiusMedium,
          sigmaY: LiquidGlassTheme.blurRadiusMedium,
        ),
        child: Container(
          decoration: BoxDecoration(
            color: AppColors.backgroundDark.withValues(alpha: 0.35),
          ),
          child: child,
        ),
      ),
    );
  }

  @override
  bool shouldRebuild(_PinnedHeaderDelegate oldDelegate) {
    return oldDelegate.height != height || oldDelegate.child != child;
  }
}
