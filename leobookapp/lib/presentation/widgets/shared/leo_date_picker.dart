// leo_date_picker.dart: leo_date_picker.dart: Widget/screen for App — Responsive Widgets.
// Part of LeoBook App — Responsive Widgets
//
// Classes: LeoDatePicker, _LeoDatePickerState

import 'package:flutter/material.dart';
import '../../../core/constants/app_colors.dart';

class LeoDatePicker extends StatefulWidget {
  final DateTime initialDate;
  final Function(DateTime) onDateSelected;
  final DateTime? lastDate;

  const LeoDatePicker({
    super.key,
    required this.initialDate,
    required this.onDateSelected,
    this.lastDate,
  });

  static Future<DateTime?> show(
    BuildContext context,
    DateTime current, {
    DateTime? lastDate,
  }) {
    return showDialog<DateTime>(
      context: context,
      builder: (context) => LeoDatePicker(
        initialDate: current,
        lastDate: lastDate,
        onDateSelected: (date) => Navigator.of(context).pop(date),
      ),
    );
  }

  @override
  State<LeoDatePicker> createState() => _LeoDatePickerState();
}

class _LeoDatePickerState extends State<LeoDatePicker> {
  late DateTime _focusedDate;
  late DateTime _selectedDate;

  final List<String> _weekDays = ["SU", "MO", "TU", "WE", "TH", "FR", "SA"];
  final List<String> _months = [
    "JANUARY",
    "FEBRUARY",
    "MARCH",
    "APRIL",
    "MAY",
    "JUNE",
    "JULY",
    "AUGUST",
    "SEPTEMBER",
    "OCTOBER",
    "NOVEMBER",
    "DECEMBER",
  ];

  @override
  void initState() {
    super.initState();
    _focusedDate = widget.initialDate;
    _selectedDate = widget.initialDate;
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      backgroundColor: Colors.transparent,
      insetPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 420),
        child: Container(
          padding: const EdgeInsets.all(24),
          decoration: BoxDecoration(
            color: AppColors.desktopSidebarBg,
            borderRadius: BorderRadius.circular(28),
            border: Border.all(color: Colors.white10),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.5),
                blurRadius: 40,
                offset: const Offset(0, 20),
              ),
            ],
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                "SELECT\nDATE",
                style: TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.w900,
                  color: Colors.white,
                  height: 1.1,
                  letterSpacing: 1.5,
                ),
              ),
              const SizedBox(height: 24),
              _buildHeader(),
              const SizedBox(height: 24),
              _buildWeekDays(),
              const SizedBox(height: 8),
              _buildCalendarGrid(),
              const SizedBox(height: 32),
              _buildActions(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        IconButton(
          onPressed: () => setState(
            () => _focusedDate = DateTime(
              _focusedDate.year,
              _focusedDate.month - 1,
            ),
          ),
          icon: const Icon(
            Icons.chevron_left_rounded,
            color: Colors.white,
            size: 20,
          ),
        ),
        Expanded(
          child: Text(
            "${_months[_focusedDate.month - 1]} ${_focusedDate.year}",
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w900,
              color: Colors.white,
              letterSpacing: 1.5,
            ),
          ),
        ),
        IconButton(
          onPressed: () => setState(
            () => _focusedDate = DateTime(
              _focusedDate.year,
              _focusedDate.month + 1,
            ),
          ),
          icon: const Icon(
            Icons.chevron_right_rounded,
            color: Colors.white,
            size: 20,
          ),
        ),
      ],
    );
  }

  Widget _buildWeekDays() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceAround,
      children: _weekDays
          .map(
            (day) => Expanded(
              child: Center(
                child: Text(
                  day,
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w900,
                    color: Colors.white.withValues(alpha: 0.3),
                    letterSpacing: 1,
                  ),
                ),
              ),
            ),
          )
          .toList(),
    );
  }

  Widget _buildCalendarGrid() {
    final daysInMonth = DateUtils.getDaysInMonth(
      _focusedDate.year,
      _focusedDate.month,
    );
    final firstDayOffset =
        DateTime(_focusedDate.year, _focusedDate.month, 1).weekday % 7;

    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 7,
        mainAxisSpacing: 4,
        crossAxisSpacing: 4,
        childAspectRatio: 1,
      ),
      itemCount: 42, // Fix grid size
      itemBuilder: (context, index) {
        final day = index - firstDayOffset + 1;
        if (day <= 0 || day > daysInMonth) return const SizedBox.shrink();

        final date = DateTime(_focusedDate.year, _focusedDate.month, day);
        final isSelected = DateUtils.isSameDay(date, _selectedDate);
        final isDisabled =
            widget.lastDate != null && date.isAfter(widget.lastDate!);

        return GestureDetector(
          onTap: isDisabled ? null : () => setState(() => _selectedDate = date),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            decoration: BoxDecoration(
              color: isSelected ? AppColors.primary : Colors.transparent,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Center(
              child: Text(
                "$day",
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: isSelected ? FontWeight.w900 : FontWeight.w600,
                  color: isDisabled
                      ? Colors.white.withValues(alpha: 0.2)
                      : isSelected
                          ? Colors.white
                          : Colors.white.withValues(alpha: 0.8),
                ),
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildActions() {
    return Row(
      children: [
        Expanded(
          child: TextButton(
            onPressed: () => Navigator.of(context).pop(),
            style: TextButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 20),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
              ),
              side: const BorderSide(color: Colors.white10),
            ),
            child: const Text(
              "CANCEL",
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w900,
                color: Colors.white,
                letterSpacing: 2,
              ),
            ),
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: ElevatedButton(
            onPressed: () => widget.onDateSelected(_selectedDate),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.primary,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(vertical: 20),
              elevation: 0,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
              ),
            ),
            child: const Text(
              "APPLY",
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w900,
                letterSpacing: 2,
              ),
            ),
          ),
        ),
      ],
    );
  }
}
