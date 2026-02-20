// footnote_section.dart: footnote_section.dart: Widget/screen for App — Widgets.
// Part of LeoBook App — Widgets
//
// Classes: FootnoteSection

import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/core/theme/liquid_glass_theme.dart';
import 'package:leobookapp/core/constants/responsive_constants.dart';

class FootnoteSection extends StatelessWidget {
  const FootnoteSection({super.key});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return ClipRect(
      child: BackdropFilter(
        filter: ImageFilter.blur(
          sigmaX: LiquidGlassTheme.blurRadiusMedium,
          sigmaY: LiquidGlassTheme.blurRadiusMedium,
        ),
        child: Container(
          padding: EdgeInsets.symmetric(
            horizontal: Responsive.sp(context, 20),
            vertical: Responsive.sp(context, 40),
          ),
          decoration: BoxDecoration(
            color:
                (isDark ? AppColors.backgroundDark : AppColors.backgroundLight)
                    .withValues(alpha: 0.5),
            border: Border(
              top: BorderSide(
                color: Colors.white.withValues(alpha: 0.1),
                width: 0.5,
              ),
            ),
          ),
          child: Column(
            children: [
              // Logo & Branding
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(
                    Icons.sports_soccer,
                    color: AppColors.primary,
                    size: Responsive.sp(context, 18),
                  ),
                  SizedBox(width: Responsive.sp(context, 6)),
                  Text(
                    "LEOBOOK",
                    style: TextStyle(
                      fontSize: Responsive.sp(context, 14),
                      fontWeight: FontWeight.w900,
                      color: isDark ? Colors.white : AppColors.textDark,
                      letterSpacing: 1.5,
                    ),
                  ),
                ],
              ),
              SizedBox(height: Responsive.sp(context, 4)),
              Text(
                "PREMIUM SPORTS INSIGHTS",
                style: TextStyle(
                  fontSize: Responsive.sp(context, 7),
                  fontWeight: FontWeight.w900,
                  color: AppColors.primary,
                  letterSpacing: 2.0,
                ),
              ),
              SizedBox(height: Responsive.sp(context, 32)),

              // Footer Links Grid
              GridView.count(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                crossAxisCount: 2,
                childAspectRatio: 5,
                crossAxisSpacing: Responsive.sp(context, 16),
                mainAxisSpacing: Responsive.sp(context, 8),
                children: [
                  _buildFooterLink(context, "ABOUT US"),
                  _buildFooterLink(context, "CONTACT US"),
                  _buildFooterLink(context, "TERMS & CONDITIONS"),
                  _buildFooterLink(context, "PRIVACY POLICY"),
                  _buildFooterLink(
                    context,
                    "RESPONSIBLE GAMBLING",
                    fullWidth: true,
                  ),
                ],
              ),
              SizedBox(height: Responsive.sp(context, 32)),

              // Social Icons
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  _buildSocialIcon(context, Icons.facebook),
                  _buildSocialIcon(context, Icons.alternate_email_rounded),
                  _buildSocialIcon(context, Icons.camera_alt_rounded),
                ],
              ),
              SizedBox(height: Responsive.sp(context, 32)),

              // Copyright
              Text(
                "© 2026 LEOBOOK SPORTS. ALL RIGHTS RESERVED.",
                style: TextStyle(
                  fontSize: Responsive.sp(context, 6),
                  fontWeight: FontWeight.w900,
                  color: AppColors.textGrey.withValues(alpha: 0.5),
                  letterSpacing: 1.0,
                ),
              ),
              SizedBox(height: Responsive.sp(context, 12)),

              // Disclaimers
              Container(
                padding: EdgeInsets.symmetric(
                  horizontal: Responsive.sp(context, 14),
                  vertical: Responsive.sp(context, 10),
                ),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.05),
                  borderRadius:
                      BorderRadius.circular(Responsive.sp(context, 12)),
                  border: Border.all(
                    color: Colors.white.withValues(alpha: 0.1),
                    width: 0.5,
                  ),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Container(
                      padding: EdgeInsets.symmetric(
                        horizontal: Responsive.sp(context, 6),
                        vertical: Responsive.sp(context, 2),
                      ),
                      decoration: BoxDecoration(
                        border: Border.all(
                          color: AppColors.textGrey.withValues(alpha: 0.4),
                          width: 0.5,
                        ),
                        borderRadius:
                            BorderRadius.circular(Responsive.sp(context, 4)),
                      ),
                      child: Text(
                        "18+",
                        style: TextStyle(
                          fontSize: Responsive.sp(context, 7),
                          fontWeight: FontWeight.w900,
                          color: AppColors.textGrey,
                        ),
                      ),
                    ),
                    SizedBox(width: Responsive.sp(context, 10)),
                    Expanded(
                      child: Text(
                        "PLAY RESPONSIBLY. GAMBLING CAN BE ADDICTIVE. KNOW YOUR LIMITS.",
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          fontSize: Responsive.sp(context, 6),
                          fontWeight: FontWeight.w900,
                          color: AppColors.textGrey.withValues(alpha: 0.6),
                          height: 1.4,
                          letterSpacing: 0.5,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildFooterLink(
    BuildContext context,
    String title, {
    bool fullWidth = false,
  }) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Center(
      child: Text(
        title,
        style: TextStyle(
          fontSize: Responsive.sp(context, 8),
          fontWeight: FontWeight.w900,
          color: isDark ? Colors.white38 : Colors.black45,
          letterSpacing: 0.5,
        ),
      ),
    );
  }

  Widget _buildSocialIcon(BuildContext context, IconData icon) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      margin: EdgeInsets.symmetric(horizontal: Responsive.sp(context, 10)),
      padding: EdgeInsets.all(Responsive.sp(context, 10)),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.05),
        shape: BoxShape.circle,
        border: Border.all(
          color: Colors.white.withValues(alpha: 0.1),
          width: 0.5,
        ),
      ),
      child: Icon(
        icon,
        size: Responsive.sp(context, 14),
        color: isDark ? Colors.white38 : Colors.black26,
      ),
    );
  }
}
