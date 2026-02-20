// user_state.dart: user_state.dart: Widget/screen for App — State Management (Cubit).
// Part of LeoBook App — State Management (Cubit)
//
// Classes: UserState, UserInitial, UserAuthenticated

part of 'user_cubit.dart';

abstract class UserState extends Equatable {
  final UserModel user;
  const UserState({required this.user});

  @override
  List<Object> get props => [user];
}

class UserInitial extends UserState {
  const UserInitial({required super.user});
}

class UserAuthenticated extends UserState {
  const UserAuthenticated({required super.user});
}
