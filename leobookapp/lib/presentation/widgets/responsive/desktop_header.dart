import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../core/constants/app_colors.dart';
import '../../../logic/cubit/home_cubit.dart';
import '../../../logic/cubit/search_cubit.dart';
import '../../screens/search_screen.dart';
import 'leo_date_picker.dart';

class DesktopHeader extends StatelessWidget {
  const DesktopHeader({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 80,
      padding: const EdgeInsets.symmetric(horizontal: 32),
      decoration: const BoxDecoration(
        color: AppColors.desktopHeaderBg,
        border: Border(bottom: BorderSide(color: Colors.white10)),
      ),
      child: Row(
        children: [
          // Search Bar
          Expanded(
            flex: 2,
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 500),
              child: GestureDetector(
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
                child: AbsorbPointer(
                  child: TextField(
                    readOnly: true,
                    style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: Colors.white,
                    ),
                    decoration: InputDecoration(
                      hintText: "SEARCH MATCHES, TEAMS OR LEAGUES...",
                      hintStyle: const TextStyle(
                        color: Colors.white24,
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                        letterSpacing: 1.2,
                      ),
                      prefixIcon: const Icon(
                        Icons.search_rounded,
                        color: Colors.white38,
                        size: 22,
                      ),
                      filled: true,
                      fillColor: AppColors.desktopSearchFill,
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(16),
                        borderSide: BorderSide.none,
                      ),
                      contentPadding: const EdgeInsets.symmetric(vertical: 0),
                    ),
                  ),
                ),
              ),
            ),
          ),
          const Spacer(),
          // Action Buttons
          Row(
            children: [
              _buildDateTrigger(context),
              const SizedBox(width: 16),
              _buildIconButton(Icons.notifications_none_rounded),
              const SizedBox(width: 16),
              Container(width: 1, height: 32, color: Colors.white10),
              const SizedBox(width: 24),
              _buildBalance(),
              const SizedBox(width: 16),
              _buildAvatar(),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildDateTrigger(BuildContext context) {
    return BlocBuilder<HomeCubit, HomeState>(
      builder: (context, state) {
        final currentDate =
            state is HomeLoaded ? state.selectedDate : DateTime.now();
        return GestureDetector(
          onTap: () async {
            final date = await LeoDatePicker.show(context, currentDate);
            if (date != null && context.mounted) {
              context.read<HomeCubit>().updateDate(date);
            }
          },
          child: Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: AppColors.desktopSearchFill,
              borderRadius: BorderRadius.circular(14),
            ),
            child: const Center(
              child: Icon(
                Icons.calendar_today_rounded,
                color: Colors.white54,
                size: 20,
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildIconButton(IconData icon) {
    return Container(
      width: 44,
      height: 44,
      decoration: BoxDecoration(
        color: AppColors.desktopSearchFill,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Center(child: Icon(icon, color: Colors.white54, size: 22)),
    );
  }

  Widget _buildBalance() {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Text(
          "BALANCE",
          style: TextStyle(
            fontSize: 10,
            fontWeight: FontWeight.w900,
            color: Colors.white.withValues(alpha: 0.3),
            letterSpacing: 1.5,
          ),
        ),
        const Text(
          "₦12,450.00",
          style: TextStyle(
            fontSize: 15,
            fontWeight: FontWeight.w900,
            color: Colors.white,
          ),
        ),
      ],
    );
  }

  Widget _buildAvatar() {
    return Container(
      width: 48,
      height: 48,
      padding: const EdgeInsets.all(2),
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        border: Border.all(color: Colors.white10, width: 1),
      ),
      child: const Center(
        child: Icon(
          Icons.person_rounded,
          color: Colors.white24,
          size: 24,
        ),
      ),
    );
  }
}
