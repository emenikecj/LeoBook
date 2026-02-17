import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:leobookapp/logic/cubit/home_cubit.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/core/utils/match_sorter.dart';
import '../widgets/match_card.dart';
import '../widgets/featured_carousel.dart';
import '../widgets/news_feed.dart';
import '../widgets/footnote_section.dart';
import '../widgets/responsive/desktop_home_content.dart';
import '../widgets/responsive/category_bar.dart';
import '../widgets/responsive/top_predictions_grid.dart';
import '../../logic/cubit/search_cubit.dart';
import 'search_screen.dart';

class HomeScreen extends StatefulWidget {
  final bool isSidebarExpanded;
  const HomeScreen({super.key, this.isSidebarExpanded = true});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final isDesktop = MediaQuery.of(context).size.width > 1024;

    return Scaffold(
      backgroundColor: isDesktop ? AppColors.backgroundDark : null,
      body: BlocBuilder<HomeCubit, HomeState>(
        builder: (context, state) {
          if (state is HomeLoading) {
            return const Center(child: CircularProgressIndicator());
          } else if (state is HomeLoaded) {
            if (isDesktop) {
              return DesktopHomeContent(
                state: state,
                isSidebarExpanded: widget.isSidebarExpanded,
              );
            }

            return SafeArea(
              child: RefreshIndicator(
                onRefresh: () async {
                  context.read<HomeCubit>().loadDashboard();
                },
                child: CustomScrollView(
                  slivers: [
                    SliverPadding(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 16, vertical: 16),
                      sliver: SliverToBoxAdapter(
                        child: Row(
                          children: [
                            const Expanded(child: CategoryBar()),
                            const SizedBox(width: 12),
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
                                padding: const EdgeInsets.all(12),
                                decoration: BoxDecoration(
                                  color: isDark
                                      ? Colors.white.withValues(alpha: 0.05)
                                      : Colors.black.withValues(alpha: 0.05),
                                  borderRadius: BorderRadius.circular(14),
                                ),
                                child: Icon(
                                  Icons.search_rounded,
                                  color:
                                      isDark ? Colors.white70 : Colors.black54,
                                  size: 22,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SliverPadding(
                      padding: EdgeInsets.symmetric(horizontal: 16),
                      sliver: SliverToBoxAdapter(
                        child: TopPredictionsGrid(),
                      ),
                    ),
                    const SliverToBoxAdapter(child: SizedBox(height: 24)),
                    SliverToBoxAdapter(
                      child: FeaturedCarousel(
                        matches: state.featuredMatches,
                        recommendations: state.filteredRecommendations,
                        allMatches: state.allMatches,
                      ),
                    ),
                    const SliverToBoxAdapter(child: SizedBox(height: 16)),
                    SliverToBoxAdapter(child: NewsFeed(news: state.news)),
                    SliverPadding(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      sliver: SliverPersistentHeader(
                        pinned: true,
                        delegate: _StickyTabBarDelegate(
                          TabBar(
                            controller: _tabController,
                            indicatorColor: AppColors.primary,
                            indicatorWeight: 3,
                            labelColor: AppColors.primary,
                            unselectedLabelColor:
                                isDark ? Colors.white60 : AppColors.textGrey,
                            labelStyle: const TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w900,
                              letterSpacing: 1.0,
                            ),
                            tabs: const [
                              Tab(text: "ALL"),
                              Tab(text: "FINISHED"),
                              Tab(text: "SCHEDULED"),
                            ],
                          ),
                          isDark,
                        ),
                      ),
                    ),
                    SliverFillRemaining(
                      child: TabBarView(
                        controller: _tabController,
                        children: [
                          _buildMatchList(
                            state.filteredMatches,
                            MatchTabType.all,
                            isDark,
                          ),
                          _buildMatchList(
                            state.filteredMatches,
                            MatchTabType.finished,
                            isDark,
                          ),
                          _buildMatchList(
                            state.filteredMatches,
                            MatchTabType.scheduled,
                            isDark,
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            );
          } else if (state is HomeError) {
            return Center(child: Text(state.message));
          }
          return Container();
        },
      ),
    );
  }

  Widget _buildMatchList(
    List<dynamic> matches,
    MatchTabType type,
    bool isDark,
  ) {
    final sortedItems = MatchSorter.getSortedMatches(matches.cast(), type);

    if (sortedItems.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.sports_soccer_rounded,
              size: 48,
              color: isDark ? Colors.white24 : Colors.black12,
            ),
            const SizedBox(height: 16),
            Text(
              "No matches found",
              style: TextStyle(
                color: isDark ? Colors.white38 : Colors.black38,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      physics: const NeverScrollableScrollPhysics(),
      itemCount: sortedItems.length + 1, // +1 for footnote
      itemBuilder: (context, index) {
        if (index == sortedItems.length) {
          return const FootnoteSection();
        }

        final item = sortedItems[index];

        if (item is MatchGroupHeader) {
          return Padding(
            padding: const EdgeInsets.fromLTRB(24, 24, 24, 8),
            child: Row(
              children: [
                Container(
                  width: 4,
                  height: 14,
                  decoration: BoxDecoration(
                    color: AppColors.primary,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  item.title.toUpperCase(),
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w900,
                    color: isDark ? Colors.white70 : AppColors.textDark,
                    letterSpacing: 1.0,
                  ),
                ),
                const Spacer(),
                Container(
                  height: 1,
                  width: 100,
                  color: isDark
                      ? Colors.white10
                      : Colors.black.withValues(alpha: 0.05),
                ),
              ],
            ),
          );
        } else {
          return MatchCard(match: item);
        }
      },
    );
  }
}

class _StickyTabBarDelegate extends SliverPersistentHeaderDelegate {
  final TabBar _tabBar;
  final bool isDark;

  _StickyTabBarDelegate(this._tabBar, this.isDark);

  @override
  double get minExtent =>
      _tabBar.preferredSize.height + 1; // +1 for bottom border
  @override
  double get maxExtent => _tabBar.preferredSize.height + 1;

  @override
  Widget build(
    BuildContext context,
    double shrinkOffset,
    bool overlapsContent,
  ) {
    return Container(
      decoration: BoxDecoration(
        color: isDark ? AppColors.backgroundDark : AppColors.backgroundLight,
        border: Border(
          bottom: BorderSide(
            color:
                isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.05),
            width: 1,
          ),
        ),
      ),
      child: _tabBar,
    );
  }

  @override
  bool shouldRebuild(_StickyTabBarDelegate oldDelegate) {
    return false;
  }
}
