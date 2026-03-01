// mobile_header.dart: Standard mobile header for branding and search.
// Part of LeoBook App — Mobile Widgets

import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/core/constants/responsive_constants.dart';
import 'package:leobookapp/core/theme/liquid_glass_theme.dart';
import 'package:leobookapp/logic/cubit/search_cubit.dart';
import '../../screens/search_screen.dart';

class MobileHeader extends StatelessWidget {
  const MobileHeader({super.key});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final hp = Responsive.horizontalPadding(context);

    return ClipRect(
      child: BackdropFilter(
        filter: ImageFilter.blur(
          sigmaX: LiquidGlassTheme.blurRadiusMedium,
          sigmaY: LiquidGlassTheme.blurRadiusMedium,
        ),
        child: Container(
          height: Responsive.sp(context, 36),
          padding: EdgeInsets.symmetric(horizontal: hp),
          decoration: BoxDecoration(
            color:
                (isDark ? AppColors.backgroundDark : AppColors.backgroundLight)
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
      ),
    );
  }
}
