// home_screen.dart: Responsive home screen — dispatches to MobileHomeContent or DesktopHomeContent.
// Part of LeoBook App — Screens
//
// Classes: HomeScreen
// Uses: MobileHomeContent (mobile/), DesktopHomeContent (desktop/)

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:leobookapp/logic/cubit/home_cubit.dart';
import 'package:leobookapp/core/constants/app_colors.dart';
import 'package:leobookapp/core/constants/responsive_constants.dart';
import '../widgets/desktop/desktop_home_content.dart';
import '../widgets/mobile/mobile_home_content.dart';

class HomeScreen extends StatelessWidget {
  final VoidCallback? onViewAllPredictions;
  const HomeScreen({super.key, this.onViewAllPredictions});

  @override
  Widget build(BuildContext context) {
    final isDesktop = Responsive.isDesktop(context);

    return Scaffold(
      backgroundColor: isDesktop ? AppColors.backgroundDark : null,
      body: BlocBuilder<HomeCubit, HomeState>(
        builder: (context, state) {
          if (state is HomeLoading) {
            return const Center(child: CircularProgressIndicator());
          } else if (state is HomeLoaded) {
            if (isDesktop) {
              return DesktopHomeContent(
                state: state,
                onViewAllPredictions: onViewAllPredictions,
              );
            }
            return MobileHomeContent(
              state: state,
              onViewAllPredictions: onViewAllPredictions,
            );
          } else if (state is HomeError) {
            return Center(child: Text(state.message));
          }
          return const SizedBox.shrink();
        },
      ),
    );
  }
}
