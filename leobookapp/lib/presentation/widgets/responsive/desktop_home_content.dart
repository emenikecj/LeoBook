import 'package:flutter/material.dart';
import 'top_predictions_grid.dart';
import 'category_bar.dart';
import 'accuracy_report_card.dart';
import 'top_odds_list.dart';
import '../../../logic/cubit/home_cubit.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/responsive_constants.dart';
import '../../../core/utils/match_sorter.dart';
import 'package:leobookapp/presentation/widgets/match_card.dart';
import '../footnote_section.dart';
import 'package:leobookapp/data/models/match_model.dart';

class DesktopHomeContent extends StatefulWidget {
  final HomeLoaded state;
  final bool isSidebarExpanded;

  const DesktopHomeContent({
    super.key,
    required this.state,
    required this.isSidebarExpanded,
  });

  @override
  State<DesktopHomeContent> createState() => _DesktopHomeContentState();
}

class _DesktopHomeContentState extends State<DesktopHomeContent>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  late ScrollController _scrollController;
  final GlobalKey _tabBarKey = GlobalKey();
  final GlobalKey _footerKey = GlobalKey();
  final Map<String, GlobalKey> _sectionKeys = {};
  int _visibleMatchCount = 12;

  // Match counts for tab labels
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
    return LayoutBuilder(
      builder: (context, constraints) {
        final hPad = Responsive.horizontalPadding(constraints.maxWidth);

        return Stack(
          children: [
            CustomScrollView(
              controller: _scrollController,
              slivers: [
                SliverPersistentHeader(
                  pinned: true,
                  delegate: _PinnedHeaderDelegate(
                    height: 92,
                    child: Container(
                      color: Theme.of(context).scaffoldBackgroundColor,
                      padding: EdgeInsets.symmetric(horizontal: hPad),
                      alignment: Alignment.centerLeft,
                      child: const CategoryBar(),
                    ),
                  ),
                ),
                SliverPadding(
                  padding: EdgeInsets.fromLTRB(hPad, 0, hPad, 32),
                  sliver: SliverList(
                    delegate: SliverChildListDelegate([
                      const TopPredictionsGrid(),
                      const SizedBox(height: 48),
                      const AccuracyReportCard(),
                      const SizedBox(height: 48),
                      const TopOddsList(),
                      const SizedBox(height: 48),
                    ]),
                  ),
                ),
                SliverPersistentHeader(
                  pinned: true,
                  delegate: _PinnedHeaderDelegate(
                    height: 50,
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
                      left: hPad, right: hPad, top: 24, bottom: 24),
                  sliver: SliverToBoxAdapter(
                    child: Builder(
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

                        return _buildMatchGroupedList(type);
                      },
                    ),
                  ),
                ),
                // Footer
                SliverToBoxAdapter(
                  child: FootnoteSection(key: _footerKey),
                ),
              ],
            ),
          ],
        );
      },
    );
  }

  TabBar _buildTabBar() {
    return TabBar(
      controller: _tabController,
      isScrollable: true,
      labelPadding: const EdgeInsets.only(right: 32),
      indicatorColor: AppColors.primary,
      indicatorWeight: 4,
      dividerColor: Colors.white10,
      labelColor: Colors.white,
      unselectedLabelColor: AppColors.textGrey,
      labelStyle: const TextStyle(
        fontSize: 14,
        fontWeight: FontWeight.w900,
        letterSpacing: 1.5,
      ),
      tabs: [
        Tab(text: "ALL PREDICTIONS ($_allCount)"),
        Tab(text: "LIVE ($_liveCount)"),
        Tab(text: "FINISHED ($_finishedCount)"),
        Tab(text: "SCHEDULED ($_scheduledCount)"),
      ],
    );
  }

  // ---------- Grouped Match List ----------

  Widget _buildMatchGroupedList(MatchTabType type) {
    final items = MatchSorter.getSortedMatches(
      widget.state.filteredMatches.cast(),
      type,
    );

    if (items.isEmpty) {
      return const Center(
        child: Text(
          "No matches found for this category",
          style: TextStyle(color: AppColors.textGrey),
        ),
      );
    }

    // We clear keys only if the list changed significantly, but for simplicity
    // let's ensure we have a key for every title we encounter.
    final List<Widget> children = [];
    List<MatchModel> currentGroupMatches = [];

    void flushGroup() {
      if (currentGroupMatches.isNotEmpty) {
        final groupSnapshot = List<MatchModel>.from(currentGroupMatches);
        children.add(
          LayoutBuilder(
            builder: (context, constraints) {
              final crossAxisCount = widget.isSidebarExpanded ? 3 : 4;
              const spacing = 20.0;
              final itemWidth =
                  (constraints.maxWidth - (spacing * (crossAxisCount - 1))) /
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
                          showLeagueHeader: type != MatchTabType.all,
                        ),
                      ),
                    )
                    .toList(),
              );
            },
          ),
        );
        children.add(const SizedBox(height: 32));
        currentGroupMatches = [];
      }
    }

    for (final item in items) {
      if (item is MatchGroupHeader) {
        flushGroup();
        final key = _sectionKeys.putIfAbsent(item.title, () => GlobalKey());
        children.add(_buildSectionHeader(item.title, key));
      } else if (item is MatchModel) {
        currentGroupMatches.add(item);
      }
    }
    flushGroup();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: children,
    );
  }

  Widget _buildSectionHeader(String title, Key? key) {
    return Padding(
      key: key,
      padding: const EdgeInsets.only(bottom: 16, top: 24),
      child: Row(
        children: [
          Container(
            width: 4,
            height: 16,
            decoration: BoxDecoration(
              color: AppColors.primary,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(width: 8),
          Text(
            title.toUpperCase(),
            style: const TextStyle(
              color: Colors.white,
              fontSize: 14,
              fontWeight: FontWeight.bold,
              letterSpacing: 1.2,
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Container(
              height: 1,
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
    return child;
  }

  @override
  bool shouldRebuild(_PinnedHeaderDelegate oldDelegate) {
    return oldDelegate.height != height || oldDelegate.child != child;
  }
}
