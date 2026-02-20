// backtest_dashboard.dart: backtest_dashboard.dart: Widget/screen for App — Rule Engine Screens.
// Part of LeoBook App — Rule Engine Screens
//
// Classes: BacktestDashboard, _BacktestDashboardState

import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:leobookapp/data/models/rule_config_model.dart';
import 'package:leobookapp/data/services/leo_service.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'rule_editor_screen.dart';

class BacktestDashboard extends StatefulWidget {
  const BacktestDashboard({super.key});

  @override
  State<BacktestDashboard> createState() => _BacktestDashboardState();
}

class _BacktestDashboardState extends State<BacktestDashboard> {
  final LeoService _leoService = LeoService();
  bool _isLoading = false;
  List<Map<String, dynamic>> _results = [];
  RuleConfigModel? _currentConfig;

  @override
  void initState() {
    super.initState();
    if (!kIsWeb) _loadInitialData();
  }

  Future<void> _loadInitialData() async {
    setState(() => _isLoading = true);
    _currentConfig = await _leoService.loadRuleConfig();
    if (_currentConfig != null) {
      await _refreshResults();
    }
    setState(() => _isLoading = false);
  }

  Future<void> _refreshResults() async {
    if (_currentConfig == null) return;
    try {
      if (mounted) setState(() => _isLoading = true);
      // We load the CSV produced by the Python script
      final results = await _leoService.getBacktestResults(
        _currentConfig!.name,
      );
      if (mounted) {
        setState(() {
          _results = results;
          _isLoading = false;
        });
      }
    } catch (e) {
      debugPrint("Error loading results: $e");
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _runBacktest() async {
    if (_currentConfig == null) return;

    setState(() => _isLoading = true);
    try {
      await _leoService.triggerBacktest(_currentConfig!);

      // In a real app, we'd listen for a "done" signal or file change
      // For now, we simulate a wait while the python script (hypothetically) runs
      // Since we don't have the real-time python runner hooked up yet in this demo flow,
      // we'll just show a message.
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Backtest Triggered! Check terminal for Python output (once integrated).',
            ),
          ),
        );
      }

      // Simulate result loading after a delay (assuming python script runs fast or we mock it)
      await Future.delayed(const Duration(seconds: 2));
      await _refreshResults();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error triggering backtest: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDesktop = MediaQuery.of(context).size.width > 1024;
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Scaffold(
      backgroundColor: isDark ? AppColors.backgroundDark : Colors.white,
      // Removed standard AppBar, using SliverAppBar below

      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : CustomScrollView(
              slivers: [
                _buildSliverAppBar(isDesktop, isDark),
                SliverPadding(
                  padding: EdgeInsets.all(isDesktop ? 32 : 16),
                  sliver: SliverToBoxAdapter(
                    child: Center(
                      child: ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 1000),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            if (isDesktop) ...[
                              Row(
                                mainAxisAlignment:
                                    MainAxisAlignment.spaceBetween,
                                children: [
                                  const Text(
                                    "RULE ENGINE",
                                    style: TextStyle(
                                      fontSize: 24,
                                      fontWeight: FontWeight.w900,
                                      color: Colors.white,
                                      letterSpacing: -1,
                                      fontStyle: FontStyle.italic,
                                    ),
                                  ),
                                  Row(
                                    children: [
                                      _buildHeaderAction(
                                        Icons.settings_outlined,
                                        "EDITOR",
                                        () async {
                                          await Navigator.push(
                                            context,
                                            MaterialPageRoute(
                                              builder: (context) =>
                                                  const RuleEditorScreen(),
                                            ),
                                          );
                                          _loadInitialData();
                                        },
                                      ),
                                      const SizedBox(width: 12),
                                      _buildHeaderAction(
                                        Icons.refresh,
                                        "REFRESH",
                                        _refreshResults,
                                      ),
                                    ],
                                  ),
                                ],
                              ),
                              const SizedBox(height: 32),
                            ],
                            _buildSummaryCard(isDesktop),
                            const SizedBox(height: 32),
                            const Text(
                              "HISTORICAL RESULTS",
                              style: TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w900,
                                color: AppColors.textGrey,
                                letterSpacing: 2,
                              ),
                            ),
                            const SizedBox(height: 16),
                            if (isDesktop)
                              _buildResultsGrid()
                            else
                              _buildResultsList(),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
                // Add some padding at the bottom so content isn't hidden behind FAB
                const SliverToBoxAdapter(child: SizedBox(height: 80)),
              ],
            ),
      floatingActionButtonLocation: FloatingActionButtonLocation.centerFloat,
      floatingActionButton: Padding(
        padding: const EdgeInsets.only(bottom: 16.0),
        child: FloatingActionButton.extended(
          onPressed: _runBacktest,
          backgroundColor: AppColors.primary,
          foregroundColor: Colors.white,
          elevation: 4,
          label: const Text(
            "RUN BACKTEST",
            style: TextStyle(fontWeight: FontWeight.w900, letterSpacing: 1),
          ),
          icon: const Icon(Icons.play_arrow_rounded),
        ),
      ),
    );
  }

  Widget _buildSliverAppBar(bool isDesktop, bool isDark) {
    if (isDesktop) return const SliverToBoxAdapter(child: SizedBox.shrink());

    return SliverAppBar(
      expandedHeight: 120.0,
      floating: false,
      pinned: true,
      backgroundColor: isDark ? AppColors.backgroundDark : Colors.white,
      surfaceTintColor: Colors.transparent,
      actions: [
        IconButton(
          icon: const Icon(Icons.settings),
          onPressed: () async {
            await Navigator.push(
              context,
              MaterialPageRoute(
                builder: (context) => const RuleEditorScreen(),
              ),
            );
            _loadInitialData();
          },
        ),
        IconButton(
          icon: const Icon(Icons.refresh),
          onPressed: _refreshResults,
        ),
      ],
      flexibleSpace: FlexibleSpaceBar(
        titlePadding: const EdgeInsets.only(left: 16, bottom: 16),
        title: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              "RULE ENGINE",
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w900,
                color: AppColors.primary.withValues(alpha: 0.8),
                letterSpacing: 2,
              ),
            ),
            const Text(
              "Dashboard",
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w900,
                color: Colors.white,
                letterSpacing: -0.5,
              ),
            ),
          ],
        ),
        background: Stack(
          fit: StackFit.expand,
          children: [
            Container(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [
                    AppColors.primary.withValues(alpha: 0.15),
                    AppColors.backgroundDark,
                  ],
                ),
              ),
            ),
            Positioned(
              right: -20,
              top: -20,
              child: Icon(
                Icons.analytics,
                size: 120,
                color: Colors.white.withValues(alpha: 0.05),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHeaderAction(IconData icon, String label, VoidCallback onTap) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        decoration: BoxDecoration(
          color: AppColors.surfaceDark,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: Colors.white10),
        ),
        child: Row(
          children: [
            Icon(icon, color: Colors.white70, size: 18),
            const SizedBox(width: 8),
            Text(
              label,
              style: const TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w900,
                color: Colors.white70,
                letterSpacing: 1,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSummaryCard(bool isDesktop) {
    int total = _results.length;
    int correct = _results.where((r) => r['outcome_correct'] == 'True').length;

    return Container(
      padding: EdgeInsets.all(isDesktop ? 32 : 16),
      decoration: BoxDecoration(
        color: AppColors.surfaceDark,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        children: [
          Row(
            children: [
              const Icon(
                Icons.analytics_outlined,
                color: AppColors.primary,
                size: 20,
              ),
              const SizedBox(width: 8),
              Text(
                "CONFIG: ${_currentConfig?.name.toUpperCase() ?? 'DEFAULT'}",
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w900,
                  color: AppColors.textGrey,
                  letterSpacing: 1.5,
                ),
              ),
            ],
          ),
          const SizedBox(height: 24),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _statItem("TOTAL MATCHES", "$total"),
              _statItem(
                "WIN RATE",
                isNaN(correct / total)
                    ? "N/A"
                    : "${(correct / total * 100).toStringAsFixed(1)}%",
              ),
              _statItem("PROFIT/LOSS", "N/A"),
            ],
          ),
        ],
      ),
    );
  }

  bool isNaN(double v) => v.isNaN || v.isInfinite;

  Widget _statItem(String label, String value) {
    final isPrimary = label == "WIN RATE";
    return Column(
      children: [
        Text(
          value,
          style: TextStyle(
            fontSize: isPrimary ? 32 : 24,
            fontWeight: FontWeight.w900,
            color: isPrimary ? AppColors.successGreen : Colors.white,
            fontStyle: FontStyle.italic,
          ),
        ),
        Text(
          label,
          style: const TextStyle(
            color: AppColors.textGrey,
            fontSize: 10,
            fontWeight: FontWeight.w900,
            letterSpacing: 1,
          ),
        ),
      ],
    );
  }

  Widget _buildResultsGrid() {
    if (_results.isEmpty) {
      return const Center(
        child: Text(
          "No backtest results found. Run a backtest!",
          style: TextStyle(color: AppColors.textGrey),
        ),
      );
    }
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 3,
        crossAxisSpacing: 16,
        mainAxisSpacing: 16,
        childAspectRatio: 2.2,
      ),
      itemCount: _results.length,
      itemBuilder: (context, index) {
        final row = _results[index];
        final isWin = row['outcome_correct'] == 'True';
        return Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppColors.backgroundDark.withValues(alpha: 0.5),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: isWin
                  ? AppColors.successGreen.withValues(alpha: 0.2)
                  : Colors.white10,
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    "MATCH #${index + 1}",
                    style: const TextStyle(
                      fontSize: 9,
                      fontWeight: FontWeight.w900,
                      color: AppColors.textGrey,
                    ),
                  ),
                  if (isWin)
                    const Icon(
                      Icons.check_circle_rounded,
                      color: AppColors.successGreen,
                      size: 14,
                    ),
                ],
              ),
              const Spacer(),
              Text(
                "${row['home_team']} VS ${row['away_team']}".toUpperCase(),
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                  color: Colors.white,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 4),
              Text(
                "PRED: ${row['prediction']} · ACTUAL: ${row['actual_score']}",
                style: const TextStyle(
                  fontSize: 10,
                  color: AppColors.textGrey,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildResultsList() {
    if (_results.isEmpty) {
      return const Center(
        child: Text(
          "No backtest results found. Run a backtest!",
          style: TextStyle(color: AppColors.textGrey),
        ),
      );
    }
    return ListView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: _results.length,
      itemBuilder: (context, index) {
        final row = _results[index];
        final isWin = row['outcome_correct'] == 'True';
        return Card(
          margin: const EdgeInsets.only(bottom: 12),
          color: AppColors.surfaceDark,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          child: ListTile(
            title: Text(
              "${row['home_team']} vs ${row['away_team']}",
              style: const TextStyle(fontWeight: FontWeight.bold),
            ),
            subtitle: Text(
              "Pred: ${row['prediction']} | Actual: ${row['actual_score']}",
              style: const TextStyle(fontSize: 12),
            ),
            trailing: isWin
                ? const Icon(Icons.check_circle, color: AppColors.successGreen)
                : const Icon(Icons.cancel, color: AppColors.liveRed),
          ),
        );
      },
    );
  }
}
