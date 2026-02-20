// leo_tab.dart: leo_tab.dart: Widget/screen for App — Responsive Widgets.
// Part of LeoBook App — Responsive Widgets
//
// Classes: LeoTab, _LeoTabState

import 'package:flutter/material.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/responsive_constants.dart';

class LeoTab extends StatefulWidget {
  final String text;
  final bool isSelected;
  final IconData? icon;

  const LeoTab({
    super.key,
    required this.text,
    this.isSelected = false,
    this.icon,
  });

  @override
  State<LeoTab> createState() => _LeoTabState();
}

class _LeoTabState extends State<LeoTab> {
  bool _isHovered = false;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      onEnter: (_) => setState(() => _isHovered = true),
      onExit: (_) => setState(() => _isHovered = false),
      child: AnimatedScale(
        scale: _isHovered ? 1.05 : 1.0,
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOutCubic,
        child: Container(
          padding: EdgeInsets.symmetric(
            vertical: Responsive.sp(context, 4),
            horizontal: Responsive.sp(context, 4),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (widget.icon != null) ...[
                Icon(
                  widget.icon,
                  size: Responsive.sp(context, 10),
                  color: _getColor(),
                ),
                SizedBox(width: Responsive.sp(context, 4)),
              ],
              Text(
                widget.text.toUpperCase(),
                style: TextStyle(
                  color: _getColor(),
                  // font size is handled by TabBar's labelStyle usually,
                  // but we replicate here for hover consistency if needed
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Color _getColor() {
    if (widget.isSelected) return AppColors.primary;
    if (_isHovered) return AppColors.primary.withValues(alpha: 0.8);
    return Colors.white60; // Default unselected
  }
}
