// account_screen.dart: account_screen.dart: Widget/screen for App — Screens.
// Part of LeoBook App — Screens
//
// Classes: AccountScreen

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/logic/cubit/user_cubit.dart';

class AccountScreen extends StatelessWidget {
  const AccountScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final isDesktop = MediaQuery.of(context).size.width > 1024;
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Scaffold(
      backgroundColor: isDark
          ? AppColors.backgroundDark
          : AppColors.backgroundLight,
      body: SafeArea(
        child: BlocBuilder<UserCubit, UserState>(
          builder: (context, state) {
            final user = state.user;
            return SingleChildScrollView(
              padding: EdgeInsets.symmetric(
                horizontal: isDesktop ? 64 : 24.0,
                vertical: 32,
              ),
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 900),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        "MY ACCOUNT",
                        style: TextStyle(
                          fontSize: isDesktop ? 40 : 32,
                          fontWeight: FontWeight.w900,
                          letterSpacing: -1.5,
                          color: Colors.white,
                          fontStyle: FontStyle.italic,
                        ),
                      ),
                      const SizedBox(height: 32),
                      _buildProfileCard(context, user, isDesktop),
                      const SizedBox(height: 48),
                      const Text(
                        "ACCOUNT SETTINGS",
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w900,
                          color: AppColors.textGrey,
                          letterSpacing: 2,
                        ),
                      ),
                      const SizedBox(height: 16),
                      if (isDesktop)
                        GridView.count(
                          shrinkWrap: true,
                          physics: const NeverScrollableScrollPhysics(),
                          crossAxisCount: 2,
                          crossAxisSpacing: 24,
                          mainAxisSpacing: 16,
                          childAspectRatio: 4,
                          children: [
                            _buildSettingsItem(
                              context,
                              icon: Icons.notifications_outlined,
                              title: "Notifications",
                              onTap: () {},
                            ),
                            _buildSettingsItem(
                              context,
                              icon: Icons.language,
                              title: "Language",
                              subtitle: "English",
                              onTap: () {},
                            ),
                            _buildSettingsItem(
                              context,
                              icon: Icons.help_outline,
                              title: "Support",
                              onTap: () {},
                            ),
                            _buildSettingsItem(
                              context,
                              icon: Icons.security_rounded,
                              title: "Security & Privacy",
                              onTap: () {},
                            ),
                          ],
                        )
                      else ...[
                        _buildSettingsItem(
                          context,
                          icon: Icons.notifications_outlined,
                          title: "Notifications",
                          onTap: () {},
                        ),
                        _buildSettingsItem(
                          context,
                          icon: Icons.language,
                          title: "Language",
                          subtitle: "English",
                          onTap: () {},
                        ),
                        _buildSettingsItem(
                          context,
                          icon: Icons.help_outline,
                          title: "Support",
                          onTap: () {},
                        ),
                      ],
                      const SizedBox(height: 48),
                      SizedBox(
                        width: isDesktop ? 200 : double.infinity,
                        child: OutlinedButton.icon(
                          onPressed: () {
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(content: Text("Logged out")),
                            );
                          },
                          icon: const Icon(
                            Icons.logout,
                            color: AppColors.liveRed,
                          ),
                          label: const Text(
                            "LOG OUT",
                            style: TextStyle(
                              color: AppColors.liveRed,
                              fontWeight: FontWeight.w900,
                              fontSize: 12,
                              letterSpacing: 1,
                            ),
                          ),
                          style: OutlinedButton.styleFrom(
                            side: const BorderSide(color: AppColors.liveRed),
                            padding: const EdgeInsets.symmetric(vertical: 20),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(16),
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            );
          },
        ),
      ),
    );
  }

  Widget _buildProfileCard(BuildContext context, dynamic user, bool isDesktop) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      padding: EdgeInsets.all(isDesktop ? 32 : 20),
      decoration: BoxDecoration(
        color: isDark
            ? Colors.white.withValues(alpha: 0.06)
            : Colors.white.withValues(alpha: 0.85),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(
          color: isDark
              ? Colors.white.withValues(alpha: 0.08)
              : Colors.black.withValues(alpha: 0.06),
        ),
      ),
      child: Row(
        children: [
          CircleAvatar(
            radius: isDesktop ? 44 : 30,
            backgroundColor: AppColors.primary.withValues(alpha: 0.1),
            child: Text(
              user.id.length >= 2
                  ? user.id.substring(0, 2).toUpperCase()
                  : user.id.toUpperCase(),
              style: TextStyle(
                fontSize: isDesktop ? 28 : 20,
                fontWeight: FontWeight.w900,
                color: AppColors.primary,
              ),
            ),
          ),
          const SizedBox(width: 24),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  user.isPro ? "PRO MEMBER" : "FREE USER",
                  style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w900,
                    letterSpacing: 2,
                    color: AppColors.primary,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  "LEOBOOK ID: ${user.id.toUpperCase()}",
                  style: TextStyle(
                    fontSize: isDesktop ? 24 : 16,
                    fontWeight: FontWeight.w900,
                    color: Colors.white,
                  ),
                ),
              ],
            ),
          ),
          if (user.isPro)
            const Icon(Icons.verified, color: AppColors.primary, size: 28)
          else
            ElevatedButton(
              onPressed: () {},
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primary,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(
                  horizontal: 24,
                  vertical: 16,
                ),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              child: const Text(
                "UPGRADE TO PRO",
                style: TextStyle(fontSize: 10, fontWeight: FontWeight.w900),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildSettingsItem(
    BuildContext context, {
    required IconData icon,
    required String title,
    String? subtitle,
    required VoidCallback onTap,
  }) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return ListTile(
      onTap: onTap,
      contentPadding: EdgeInsets.zero,
      leading: Container(
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: isDark
              ? Colors.white.withValues(alpha: 0.06)
              : AppColors.primary.withValues(alpha: 0.06),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isDark
                ? Colors.white.withValues(alpha: 0.08)
                : AppColors.primary.withValues(alpha: 0.08),
          ),
        ),
        child: Icon(
          icon,
          color: isDark ? Colors.white : AppColors.primary,
          size: 20,
        ),
      ),
      title: Text(title, style: const TextStyle(fontWeight: FontWeight.w600)),
      trailing: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (subtitle != null)
            Text(
              subtitle,
              style: const TextStyle(color: AppColors.textGrey, fontSize: 12),
            ),
          const SizedBox(width: 8),
          const Icon(
            Icons.arrow_forward_ios,
            size: 14,
            color: AppColors.textGrey,
          ),
        ],
      ),
    );
  }
}
