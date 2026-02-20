// user_model.dart: user_model.dart: Widget/screen for App — Data Models.
// Part of LeoBook App — Data Models
//
// Classes: UserModel

enum UserTier { unregistered, lite, pro }

class UserModel {
  final String id;
  final String? email; // Optional for unregistered
  final UserTier tier;
  final bool isEmailVerified;

  const UserModel({
    required this.id,
    this.email,
    this.tier = UserTier.unregistered,
    this.isEmailVerified = false,
  });

  bool get canCreateCustomRules =>
      tier == UserTier.lite || tier == UserTier.pro;
  bool get canRunBacktests => tier == UserTier.lite || tier == UserTier.pro;
  bool get canAutomateBetting => tier == UserTier.pro;
  bool get canAccessChapter2 => tier == UserTier.pro;
  bool get isPro => tier == UserTier.pro;

  factory UserModel.guest() {
    return const UserModel(id: 'guest', tier: UserTier.unregistered);
  }

  factory UserModel.lite({required String id, String? email}) {
    return UserModel(
      id: id,
      email: email,
      tier: UserTier.lite,
      isEmailVerified: true,
    );
  }

  factory UserModel.pro({required String id, String? email}) {
    return UserModel(
      id: id,
      email: email,
      tier: UserTier.pro,
      isEmailVerified: true,
    );
  }
}
