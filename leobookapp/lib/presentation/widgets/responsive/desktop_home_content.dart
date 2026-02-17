import 'package:flutter/material.dart';
import 'top_predictions_grid.dart';
import 'category_bar.dart';
import 'accuracy_report_card.dart';
import 'top_odds_list.dart';
import 'side_ruler.dart';
import '../../../logic/cubit/home_cubit.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/utils/match_sorter.dart';
import '../match_card.dart';
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
  int _visibleMatchCount = 12;

  // Match counts for tab labels
  int _allCount = 0;
  int _finishedCount = 0;
  int _scheduledCount = 0;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
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
    return Stack(
      children: [
        CustomScrollView(
          controller: _scrollController,
          slivers: [
            SliverPadding(
              padding: const EdgeInsets.symmetric(horizontal: 40, vertical: 32),
              sliver: SliverList(
                delegate: SliverChildListDelegate([
                  const CategoryBar(),
                  const SizedBox(height: 8),
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
              delegate: _StickyTabBarDelegate(
                child: Container(
                  color: Theme.of(context).scaffoldBackgroundColor,
                  padding: const EdgeInsets.symmetric(horizontal: 40),
                  alignment: Alignment.centerLeft,
                  child: _buildTabBar(),
                ),
              ),
            ),
            SliverPadding(
              padding: const EdgeInsets.only(
                  left: 40, right: 80, top: 24, bottom: 24),
              sliver: SliverToBoxAdapter(
                child: Builder(
                  builder: (context) {
                    final index = _tabController.index;
                    MatchTabType type;
                    switch (index) {
                      case 1:
                        type = MatchTabType.finished;
                        break;
                      case 2:
                        type = MatchTabType.scheduled;
                        break;
                      default:
                        type = MatchTabType.all;
                    }
                    return _buildMatchGrid(type);
                  },
                ),
              ),
            ),
            // Footer
            const SliverToBoxAdapter(
              child: FootnoteSection(),
            ),
          ],
        ),
        // Side Ruler - Positioned over the view but aligned to the right
        Positioned(
          top: 100, // Aligned closer to the TabBar area
          bottom: 80, // Aligned above the Footer
          right: 20,
          child: Center(
            child: Builder(
              builder: (context) {
                final index = _tabController.index;
                MatchTabType type;
                switch (index) {
                  case 1:
                    type = MatchTabType.finished;
                    break;
                  case 2:
                    type = MatchTabType.scheduled;
                    break;
                  default:
                    type = MatchTabType.all;
                }
                final ruler = _buildSideRuler(type);
                return ruler ?? const SizedBox.shrink();
              },
            ),
          ),
        ),
      ],
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
        Tab(text: "FINISHED ($_finishedCount)"),
        Tab(text: "SCHEDULED ($_scheduledCount)"),
      ],
    );
  }

  // ---------- Side Ruler ----------

  Widget? _buildSideRuler(MatchTabType type) {
    switch (type) {
      case MatchTabType.all:
        final leagueNames = widget.state.filteredMatches
            .map((m) => m.league ?? 'Other')
            .toSet()
            .toList()
          ..sort();
        final labels = SideRuler.alphabeticalLabels(leagueNames);
        if (labels.isEmpty) return null;
        return SideRuler(
          labels: labels,
          onLabelTapped: (idx) => _scrollToSection(idx, labels[idx], type),
        );

      case MatchTabType.finished:
        final labels = SideRuler.finishedTimeLabels();
        return SideRuler(
          labels: labels,
          onLabelTapped: (idx) => _scrollToSection(idx, labels[idx], type),
        );

      case MatchTabType.scheduled:
        final labels = SideRuler.scheduledTimeLabels();
        return SideRuler(
          labels: labels,
          onLabelTapped: (idx) => _scrollToSection(idx, labels[idx], type),
        );
    }
  }

  void _scrollToSection(int index, String label, MatchTabType type) {
    // Basic logic: Jump to a position relative to match count.
    // In a production app, we'd use GlobalKeys per section or a FixedExtentScrollController.
    // For now, we perform a smart scroll to the match grid area.
    final targetOffset = 800.0 + (index * 200.0); // Rough estimate
    _scrollController.animateTo(
      targetOffset,
      duration: const Duration(milliseconds: 500),
      curve: Curves.easeInOut,
    );
  }

  Widget _buildMatchGrid(MatchTabType type) {
    var matches = MatchSorter.getSortedMatches(
      widget.state.filteredMatches.cast(),
      type,
    ).whereType<MatchModel>().toList();

    if (matches.isEmpty) {
      return const Center(
        child: Text(
          "No matches found for this category",
          style: TextStyle(color: AppColors.textGrey),
        ),
      );
    }

    final totalMatches = matches.length;
    final displayMatches = matches.take(_visibleMatchCount).toList();
    final hasMore = totalMatches > _visibleMatchCount;

    return Column(
      children: [
        GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: widget.isSidebarExpanded ? 3 : 4,
            crossAxisSpacing: 20,
            mainAxisSpacing: 20,
            mainAxisExtent: 350,
          ),
          itemCount: displayMatches.length,
          itemBuilder: (context, index) {
            return MatchCard(match: displayMatches[index]);
          },
        ),
        if (hasMore) ...[
          const SizedBox(height: 32),
          Center(
            child: TextButton(
              onPressed: () {
                setState(() => _visibleMatchCount += 12);
              },
              style: TextButton.styleFrom(
                padding:
                    const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
                backgroundColor: Colors.white.withValues(alpha: 0.05),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(30),
                  side: BorderSide(color: Colors.white.withValues(alpha: 0.1)),
                ),
              ),
              child: const Text(
                "VIEW MORE MATCHES",
                style: TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 1.2,
                ),
              ),
            ),
          ),
        ],
        const SizedBox(height: 40),
      ],
    );
  }
}

class _StickyTabBarDelegate extends SliverPersistentHeaderDelegate {
  final Widget child;

  _StickyTabBarDelegate({required this.child});

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
    return child;
  }

  @override
  bool shouldRebuild(_StickyTabBarDelegate oldDelegate) => false;
}
