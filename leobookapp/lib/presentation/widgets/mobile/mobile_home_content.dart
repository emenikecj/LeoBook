// mobile_home_content.dart: Mobile-specific home layout with tabbed match list.
// Part of LeoBook App — Mobile Widgets
//
// Classes: MobileHomeContent, _MobileHomeContentState, _StickyTabBarDelegate
// Used by: home_screen.dart (mobile viewport branch)

import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:leobookapp/logic/cubit/home_cubit.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/core/constants/responsive_constants.dart';
import 'package:leobookapp/core/utils/match_sorter.dart';
import 'package:leobookapp/core/animations/liquid_glass_animations.dart';
import 'package:leobookapp/core/theme/liquid_glass_theme.dart';
import 'package:leobookapp/logic/cubit/search_cubit.dart';
import '../shared/match_card.dart';
import '../shared/featured_carousel.dart';
import '../shared/news_feed.dart';
import '../shared/category_bar.dart';
import '../shared/leo_tab.dart';
import '../shared/accuracy_report_card.dart';
import '../shared/footnote_section.dart';
import '../../screens/search_screen.dart';

/// Mobile home content — fullscreen scrollable layout with:
/// - Glassmorphic App Bar with search + CategoryBar
/// - Featured carousel
/// - Accuracy report card
/// - News feed
/// - Sticky tabbed match list (All / Live / Finished / Scheduled)
/// - Footnote section
class MobileHomeContent extends StatefulWidget {
  final HomeLoaded state;
  final VoidCallback? onViewAllPredictions;

  const MobileHomeContent({
    super.key,
    required this.state,
    this.onViewAllPredictions,
  });

  @override
  State<MobileHomeContent> createState() => _MobileHomeContentState();
}

class _MobileHomeContentState extends State<MobileHomeContent>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
    _tabController.addListener(_onTabChanged);
  }

  void _onTabChanged() {
    if (!_tabController.indexIsChanging) return;
    setState(() {});
  }

  @override
  void dispose() {
    _tabController.removeListener(_onTabChanged);
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final hp = Responsive.horizontalPadding(context);

    return SafeArea(
      bottom: false,
      child: RefreshIndicator(
        onRefresh: () async {
          context.read<HomeCubit>().loadDashboard();
        },
        child: CustomScrollView(
          physics: liquidScrollPhysics,
          slivers: [
            SliverAppBar(
              pinned: true,
              floating: false,
              elevation: 0,
              backgroundColor: Colors.transparent,
              expandedHeight: 0,
              toolbarHeight: Responsive.sp(context, 32),
              centerTitle: false,
              title: Padding(
                padding: EdgeInsets.symmetric(horizontal: hp),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      "LEOBOOK",
                      style: TextStyle(
                        fontSize: Responsive.sp(context, 12),
                        fontWeight: FontWeight.w900,
                        color: isDark ? Colors.white : AppColors.textDark,
                        letterSpacing: 2.0,
                      ),
                    ),
                    GestureDetector(
                      onTap: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => BlocProvider.value(
                              value: context.read<SearchCubit>(),
                              child: const SearchScreen(),
                            ),
                          ),
                        );
                      },
                      child: Container(
                        padding: EdgeInsets.all(Responsive.sp(context, 6)),
                        decoration: BoxDecoration(
                          color: isDark
                              ? Colors.white.withValues(alpha: 0.05)
                              : Colors.black.withValues(alpha: 0.05),
                          borderRadius:
                              BorderRadius.circular(Responsive.sp(context, 8)),
                        ),
                        child: Icon(
                          Icons.search_rounded,
                          color: isDark ? Colors.white70 : Colors.black54,
                          size: Responsive.sp(context, 15),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              bottom: PreferredSize(
                preferredSize: Size.fromHeight(Responsive.sp(context, 44)),
                child: const CategoryBar(),
              ),
              flexibleSpace: ClipRect(
                child: BackdropFilter(
                  filter: ImageFilter.blur(
                    sigmaX: LiquidGlassTheme.blurRadiusMedium,
                    sigmaY: LiquidGlassTheme.blurRadiusMedium,
                  ),
                  child: Container(
                    decoration: BoxDecoration(
                      color: (isDark
                              ? AppColors.backgroundDark
                              : AppColors.backgroundLight)
                          .withValues(alpha: 0.35),
                      border: Border(
                        bottom: BorderSide(
                          color: isDark
                              ? Colors.white10
                              : Colors.black.withValues(alpha: 0.04),
                          width: 1.0,
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ),
            SliverPadding(
              padding: EdgeInsets.symmetric(horizontal: hp),
              sliver: SliverToBoxAdapter(
                child: FeaturedCarousel(
                  matches: widget.state.featuredMatches,
                  recommendations: widget.state.filteredRecommendations,
                  allMatches: widget.state.allMatches,
                  onViewAll: widget.onViewAllPredictions,
                ),
              ),
            ),
            SliverPadding(
              padding: EdgeInsets.symmetric(horizontal: hp),
              sliver: SliverToBoxAdapter(
                child: Column(
                  children: [
                    SizedBox(height: Responsive.sp(context, 10)),
                    const AccuracyReportCard(),
                    SizedBox(height: Responsive.sp(context, 10)),
                  ],
                ),
              ),
            ),
            SliverToBoxAdapter(child: NewsFeed(news: widget.state.news)),
            SliverToBoxAdapter(
                child: SizedBox(height: Responsive.sp(context, 6))),
            SliverPersistentHeader(
              pinned: true,
              delegate: _StickyTabBarDelegate(
                AnimatedBuilder(
                  animation: _tabController,
                  builder: (context, _) {
                    return TabBar(
                      controller: _tabController,
                      indicatorColor: AppColors.primary,
                      indicatorWeight: 2,
                      labelColor: AppColors.primary,
                      unselectedLabelColor:
                          isDark ? Colors.white60 : AppColors.textGrey,
                      labelStyle: TextStyle(
                        fontSize: Responsive.sp(context, 10),
                        fontWeight: FontWeight.w900,
                        letterSpacing: 0.8,
                      ),
                      unselectedLabelStyle: TextStyle(
                        fontSize: Responsive.sp(context, 8),
                        fontWeight: FontWeight.w700,
                      ),
                      dividerColor: Colors.transparent,
                      labelPadding: EdgeInsets.symmetric(
                          horizontal: Responsive.sp(context, 4)),
                      tabs: [
                        Tab(
                          child: LeoTab(
                            text:
                                "ALL (${widget.state.filteredMatches.length})",
                            isSelected: _tabController.index == 0,
                          ),
                        ),
                        Tab(
                          child: LeoTab(
                            text:
                                "LIVE (${widget.state.filteredMatches.where((m) => m.isLive).length})",
                            isSelected: _tabController.index == 1,
                          ),
                        ),
                        Tab(
                          child: LeoTab(
                            text:
                                "FINISHED (${widget.state.filteredMatches.where((m) => m.isFinished).length})",
                            isSelected: _tabController.index == 2,
                          ),
                        ),
                        Tab(
                          child: LeoTab(
                            text:
                                "SCHEDULED (${widget.state.filteredMatches.where((m) => !m.isLive && !m.isFinished).length})",
                            isSelected: _tabController.index == 3,
                          ),
                        ),
                      ],
                    );
                  },
                ),
                isDark,
              ),
            ),
            SliverPadding(
              padding: EdgeInsets.symmetric(
                horizontal: hp,
                vertical: Responsive.sp(context, 8),
              ),
              sliver: Builder(
                builder: (context) {
                  final index = _tabController.index;
                  MatchTabType type;
                  bool hideLeague = false;
                  switch (index) {
                    case 1:
                      type = MatchTabType.live;
                      hideLeague = true;
                      break;
                    case 2:
                      type = MatchTabType.finished;
                      break;
                    case 3:
                      type = MatchTabType.scheduled;
                      break;
                    default:
                      type = MatchTabType.all;
                      hideLeague = true;
                  }

                  final sortedItems = MatchSorter.getSortedMatches(
                      widget.state.filteredMatches.cast(), type);

                  if (sortedItems.isEmpty) {
                    return SliverToBoxAdapter(
                      child: Padding(
                        padding: EdgeInsets.symmetric(
                            vertical: Responsive.sp(context, 40)),
                        child: Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(
                                Icons.sports_soccer_rounded,
                                size: Responsive.sp(context, 28),
                                color: isDark ? Colors.white24 : Colors.black12,
                              ),
                              SizedBox(height: Responsive.sp(context, 8)),
                              Text(
                                "No matches found",
                                style: TextStyle(
                                  fontSize: Responsive.sp(context, 10),
                                  color:
                                      isDark ? Colors.white38 : Colors.black38,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    );
                  }

                  return SliverList(
                    delegate: SliverChildBuilderDelegate(
                      (context, i) {
                        return _buildItem(sortedItems[i], isDark,
                            hideLeagueInfo: hideLeague);
                      },
                      childCount: sortedItems.length,
                    ),
                  );
                },
              ),
            ),
            SliverToBoxAdapter(
              child: SizedBox(height: Responsive.sp(context, 20)),
            ),
            const SliverToBoxAdapter(
              child: FootnoteSection(),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildItem(dynamic item, bool isDark, {bool hideLeagueInfo = false}) {
    if (item is MatchGroupHeader) {
      return Padding(
        padding: EdgeInsets.fromLTRB(
          Responsive.sp(context, 14),
          Responsive.sp(context, 12),
          Responsive.sp(context, 14),
          Responsive.sp(context, 4),
        ),
        child: Row(
          children: [
            Container(
              width: Responsive.sp(context, 2.5),
              height: Responsive.sp(context, 8),
              decoration: BoxDecoration(
                color: AppColors.primary,
                borderRadius: BorderRadius.circular(1),
                boxShadow: [
                  BoxShadow(
                    color: AppColors.primary.withValues(alpha: 0.4),
                    blurRadius: 3,
                    spreadRadius: 0,
                  ),
                ],
              ),
            ),
            SizedBox(width: Responsive.sp(context, 4)),
            Text(
              item.title.toUpperCase(),
              style: TextStyle(
                fontSize: Responsive.sp(context, 9),
                fontWeight: FontWeight.w900,
                color: isDark ? Colors.white70 : AppColors.textDark,
                letterSpacing: 0.8,
              ),
            ),
            const Spacer(),
            Flexible(
              child: Container(
                height: 0.5,
                color: isDark
                    ? Colors.white10
                    : Colors.black.withValues(alpha: 0.04),
              ),
            ),
          ],
        ),
      );
    } else {
      return MatchCard(match: item, hideLeagueInfo: hideLeagueInfo);
    }
  }
}

class _StickyTabBarDelegate extends SliverPersistentHeaderDelegate {
  final Widget _tabBar;
  final bool isDark;

  _StickyTabBarDelegate(this._tabBar, this.isDark);

  @override
  double get minExtent => 50.0;
  @override
  double get maxExtent => 50.0;

  @override
  Widget build(
    BuildContext context,
    double shrinkOffset,
    bool overlapsContent,
  ) {
    final hp = Responsive.horizontalPadding(context);
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Container(
      padding: EdgeInsets.symmetric(horizontal: hp),
      color: Colors.transparent,
      height: 50.0,
      child: Stack(
        children: [
          ClipRRect(
            borderRadius: BorderRadius.vertical(
              top: Radius.circular(Responsive.sp(context, 16)),
            ),
            child: BackdropFilter(
              filter: ImageFilter.blur(
                sigmaX: LiquidGlassTheme.blurRadiusMedium,
                sigmaY: LiquidGlassTheme.blurRadiusMedium,
              ),
              child: Container(
                height: 50.0,
                decoration: BoxDecoration(
                  color: (isDark
                          ? AppColors.backgroundDark
                          : AppColors.backgroundLight)
                      .withValues(alpha: 0.5),
                  borderRadius: BorderRadius.vertical(
                    top: Radius.circular(Responsive.sp(context, 16)),
                  ),
                  border: Border(
                    top: BorderSide(
                      color: Colors.white.withValues(alpha: 0.1),
                      width: 1.0,
                    ),
                    left: BorderSide(
                      color: Colors.white.withValues(alpha: 0.1),
                      width: 1.0,
                    ),
                    right: BorderSide(
                      color: Colors.white.withValues(alpha: 0.1),
                      width: 1.0,
                    ),
                  ),
                ),
                child: _tabBar,
              ),
            ),
          ),
        ],
      ),
    );
  }

  @override
  bool shouldRebuild(_StickyTabBarDelegate oldDelegate) {
    return false;
  }
}
