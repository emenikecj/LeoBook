import 'package:flutter/material.dart';
import '../../../core/constants/app_colors.dart';

/// A vertical ruler strip displayed on the right side of a scrollable list,
/// providing quick-jump scroll points.
///
/// For "All Predictions" tab: A-Z alphabetical labels.
/// For "Finished" tab: time labels from current hour down to 00:00.
/// For "Scheduled" tab: time labels from current hour up to 23:59.
class SideRuler extends StatelessWidget {
  /// Ordered list of labels to display (e.g., ["A", "B", "C"] or ["14:00", "13:00"]).
  final List<String> labels;

  /// Called when a label is tapped, with the label's index.
  final ValueChanged<int> onLabelTapped;

  /// Optional: the currently active/highlighted label index.
  final int? activeIndex;

  const SideRuler({
    super.key,
    required this.labels,
    required this.onLabelTapped,
    this.activeIndex,
  });

  /// Generate A-Z labels from a list of league names (first letter, unique, sorted).
  static List<String> alphabeticalLabels(List<String> leagueNames) {
    final letters = <String>{};
    for (final name in leagueNames) {
      if (name.isNotEmpty) {
        letters.add(name[0].toUpperCase());
      }
    }
    final sorted = letters.toList()..sort();
    return sorted;
  }

  /// Generate time labels descending from current hour to 00:00.
  /// E.g., if now is 14:30 → ["14:00", "13:00", ..., "00:00"]
  static List<String> finishedTimeLabels() {
    final now = DateTime.now();
    final labels = <String>[];
    for (int h = now.hour; h >= 0; h--) {
      labels.add('${h.toString().padLeft(2, '0')}:00');
    }
    return labels;
  }

  /// Generate time labels ascending from current hour to 23:00.
  /// E.g., if now is 14:30 → ["14:00", "15:00", ..., "23:00"]
  static List<String> scheduledTimeLabels() {
    final now = DateTime.now();
    final labels = <String>[];
    for (int h = now.hour; h <= 23; h++) {
      labels.add('${h.toString().padLeft(2, '0')}:00');
    }
    return labels;
  }

  @override
  Widget build(BuildContext context) {
    if (labels.isEmpty) return const SizedBox.shrink();

    return Container(
      width: 32,
      padding: const EdgeInsets.symmetric(vertical: 8),
      decoration: BoxDecoration(
        color: AppColors.desktopSearchFill.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white.withValues(alpha: 0.05)),
      ),
      child: SingleChildScrollView(
        child: Column(
          children: List.generate(labels.length, (index) {
            final isActive = activeIndex == index;
            return GestureDetector(
              onTap: () => onLabelTapped(index),
              child: Container(
                width: 32,
                padding: const EdgeInsets.symmetric(vertical: 6),
                color: Colors.transparent,
                child: Center(
                  child: Text(
                    labels[index].length > 2
                        ? labels[index].substring(0, 2)
                        : labels[index],
                    style: TextStyle(
                      fontSize: 10,
                      fontWeight: isActive ? FontWeight.w900 : FontWeight.w600,
                      color: isActive
                          ? AppColors.primary
                          : AppColors.textGrey.withValues(alpha: 0.6),
                      letterSpacing: 0.5,
                    ),
                  ),
                ),
              ),
            );
          }),
        ),
      ),
    );
  }
}
