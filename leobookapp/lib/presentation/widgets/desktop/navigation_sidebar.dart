// navigation_sidebar.dart: navigation_sidebar.dart: Widget/screen for App — Responsive Widgets.
// Part of LeoBook App — Responsive Widgets
//
// Classes: NavigationSideBar, _NavItem, _NavItemState

import 'dart:ui';
import 'package:flutter/material.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/responsive_constants.dart';
import '../../../core/theme/liquid_glass_theme.dart';

class NavigationSideBar extends StatelessWidget {
  final int currentIndex;
  final ValueChanged<int> onIndexChanged;
  final bool isExpanded;
  final VoidCallback onToggle;

  const NavigationSideBar({
    super.key,
    required this.currentIndex,
    required this.onIndexChanged,
    required this.isExpanded,
    required this.onToggle,
  });

  @override
  Widget build(BuildContext context) {
    return AnimatedSize(
      duration: LiquidGlassTheme.tabSwitchDuration,
      curve: LiquidGlassTheme.tabSwitchCurve,
      child: IntrinsicWidth(
        child: ClipRect(
          child: BackdropFilter(
            filter: ImageFilter.blur(
              sigmaX: LiquidGlassTheme.blurRadiusMedium,
              sigmaY: LiquidGlassTheme.blurRadiusMedium,
            ),
            child: Container(
              height: double.infinity,
              decoration: BoxDecoration(
                color: AppColors.backgroundDark.withValues(alpha: 0.35),
                border: Border(
                  right: BorderSide(
                    color: LiquidGlassTheme.glassBorderDark,
                    width: 0.5,
                  ),
                ),
              ),
              child: SingleChildScrollView(
                child: ConstrainedBox(
                  constraints: BoxConstraints(
                    minHeight: MediaQuery.sizeOf(context).height,
                  ),
                  child: IntrinsicHeight(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        _buildLogo(context),
                        SizedBox(height: Responsive.dp(context, 20)),
                        Padding(
                          padding: EdgeInsets.symmetric(
                              horizontal: Responsive.dp(context, 8)),
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              _NavItem(
                                icon: Icons.home_rounded,
                                label: "HOME",
                                isActive: currentIndex == 0,
                                isExpanded: isExpanded,
                                onTap: () => onIndexChanged(0),
                              ),
                              _NavItem(
                                icon: Icons.gavel_rounded,
                                label: "RULES",
                                isActive: currentIndex == 1,
                                isExpanded: isExpanded,
                                onTap: () => onIndexChanged(1),
                              ),
                              _NavItem(
                                icon: Icons.emoji_events_rounded,
                                label: "TOP",
                                isActive: currentIndex == 2,
                                isExpanded: isExpanded,
                                onTap: () => onIndexChanged(2),
                              ),
                              _NavItem(
                                icon: Icons.person_rounded,
                                label: "PROFILE",
                                isActive: currentIndex == 3,
                                isExpanded: isExpanded,
                                onTap: () => onIndexChanged(3),
                              ),
                            ],
                          ),
                        ),
                        const Spacer(),
                        if (isExpanded) _buildProCard(context),
                        _buildToggleBtn(),
                        SizedBox(height: Responsive.dp(context, 10)),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildToggleBtn() {
    return IconButton(
      onPressed: onToggle,
      icon: AnimatedRotation(
        turns: isExpanded ? 0.0 : 0.5,
        duration: LiquidGlassTheme.tabSwitchDuration,
        child: const Icon(
          Icons.keyboard_double_arrow_left,
          color: Colors.white54,
          size: 18,
        ),
      ),
    );
  }

  Widget _buildLogo(BuildContext context) {
    return Padding(
      padding: EdgeInsets.symmetric(
        horizontal:
            isExpanded ? Responsive.dp(context, 12) : Responsive.dp(context, 4),
        vertical: isExpanded
            ? Responsive.dp(context, 16)
            : Responsive.dp(context, 10),
      ),
      child: FittedBox(
        fit: BoxFit.scaleDown,
        alignment: isExpanded ? Alignment.centerLeft : Alignment.center,
        child: Row(
          mainAxisAlignment:
              isExpanded ? MainAxisAlignment.start : MainAxisAlignment.center,
          mainAxisSize: isExpanded ? MainAxisSize.max : MainAxisSize.min,
          children: [
            Container(
              padding: EdgeInsets.all(isExpanded
                  ? Responsive.dp(context, 5)
                  : Responsive.dp(context, 4)),
              decoration: BoxDecoration(
                color: AppColors.primary,
                borderRadius: BorderRadius.circular(Responsive.dp(context, 6)),
              ),
              child: Icon(
                Icons.analytics_rounded,
                color: Colors.white,
                size: isExpanded
                    ? Responsive.dp(context, 18)
                    : Responsive.dp(context, 14),
              ),
            ),
            if (isExpanded) ...[
              SizedBox(width: Responsive.dp(context, 6)),
              Text(
                "LEOBOOK",
                style: TextStyle(
                  fontSize: Responsive.dp(context, 16),
                  fontWeight: FontWeight.w900,
                  color: Colors.white,
                  fontStyle: FontStyle.italic,
                  letterSpacing: -0.5,
                ),
                overflow: TextOverflow.ellipsis,
                maxLines: 1,
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildProCard(BuildContext context) {
    return Padding(
      padding: EdgeInsets.symmetric(
        horizontal: Responsive.dp(context, 10),
        vertical: Responsive.dp(context, 14),
      ),
      child: Container(
        padding: EdgeInsets.all(Responsive.dp(context, 8)),
        decoration: BoxDecoration(
          color: AppColors.backgroundDark.withValues(alpha: 0.5),
          borderRadius: BorderRadius.circular(Responsive.dp(context, 10)),
          border:
              Border.all(color: LiquidGlassTheme.glassBorderDark, width: 0.5),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              "PREMIUM STATUS",
              style: TextStyle(
                fontSize: Responsive.dp(context, 7),
                fontWeight: FontWeight.w900,
                color: AppColors.textGrey,
                letterSpacing: 1.0,
              ),
            ),
            SizedBox(height: Responsive.dp(context, 4)),
            FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.centerLeft,
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    "PRO MEMBER",
                    style: TextStyle(
                      fontSize: Responsive.dp(context, 9),
                      fontWeight: FontWeight.bold,
                      color: AppColors.successGreen,
                    ),
                  ),
                  SizedBox(width: Responsive.dp(context, 4)),
                  Icon(Icons.verified,
                      color: AppColors.warning,
                      size: Responsive.dp(context, 12)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _NavItem extends StatefulWidget {
  final IconData icon;
  final String label;
  final bool isActive;
  final bool isExpanded;
  final VoidCallback onTap;

  const _NavItem({
    required this.icon,
    required this.label,
    required this.isActive,
    required this.isExpanded,
    required this.onTap,
  });

  @override
  State<_NavItem> createState() => _NavItemState();
}

class _NavItemState extends State<_NavItem> {
  bool _isHovered = false;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: Responsive.dp(context, 2)),
      child: MouseRegion(
        onEnter: (_) => setState(() => _isHovered = true),
        onExit: (_) => setState(() => _isHovered = false),
        child: GestureDetector(
          onTap: widget.onTap,
          child: AnimatedContainer(
            duration: LiquidGlassTheme.cardPressDuration,
            curve: LiquidGlassTheme.cardPressCurve,
            padding: EdgeInsets.symmetric(
              horizontal: widget.isExpanded
                  ? Responsive.dp(context, 10)
                  : Responsive.dp(context, 8),
              vertical: Responsive.dp(context, 8),
            ),
            decoration: BoxDecoration(
              color: widget.isActive
                  ? AppColors.primary.withValues(alpha: 0.12)
                  : (_isHovered
                      ? Colors.white.withValues(alpha: 0.04)
                      : Colors.transparent),
              borderRadius: BorderRadius.circular(Responsive.dp(context, 8)),
              border: Border.all(
                color: widget.isActive
                    ? AppColors.primary.withValues(alpha: 0.4)
                    : (_isHovered
                        ? LiquidGlassTheme.glassBorderDark
                        : Colors.transparent),
                width: 0.5,
              ),
            ),
            child: FittedBox(
              fit: BoxFit.scaleDown,
              alignment:
                  widget.isExpanded ? Alignment.centerLeft : Alignment.center,
              child: Row(
                mainAxisAlignment: widget.isExpanded
                    ? MainAxisAlignment.start
                    : MainAxisAlignment.center,
                children: [
                  Icon(
                    widget.icon,
                    color: widget.isActive ? AppColors.primary : Colors.white54,
                    size: Responsive.dp(context, 15),
                  ),
                  if (widget.isExpanded) ...[
                    SizedBox(width: Responsive.dp(context, 8)),
                    Text(
                      widget.label,
                      style: TextStyle(
                        fontSize: Responsive.dp(context, 9),
                        fontWeight: FontWeight.w700,
                        color: widget.isActive ? Colors.white : Colors.white54,
                        letterSpacing: 0.8,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
