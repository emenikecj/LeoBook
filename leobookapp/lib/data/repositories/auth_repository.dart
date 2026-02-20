// auth_repository.dart: auth_repository.dart: Widget/screen for App — Repositories.
// Part of LeoBook App — Repositories
//
// Classes: AuthRepository

import 'package:google_sign_in/google_sign_in.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:flutter/foundation.dart';

class AuthRepository {
  final SupabaseClient _supabase = Supabase.instance.client;

  /// Stream of Supabase Auth state changes
  Stream<AuthState> get authStateChanges => _supabase.auth.onAuthStateChange;

  /// Get current user
  User? get currentUser => _supabase.auth.currentUser;

  /// Sign in with Google
  Future<AuthResponse> signInWithGoogle() async {
    try {
      // 1. Initialize GoogleSignIn
      // For web, you might need a clientId from environment variables
      const webClientId = String.fromEnvironment('GOOGLE_WEB_CLIENT_ID');
      const iosClientId = String.fromEnvironment('GOOGLE_IOS_CLIENT_ID');

      final GoogleSignIn googleSignIn = GoogleSignIn(
        clientId: iosClientId.isEmpty ? null : iosClientId,
        serverClientId: webClientId.isEmpty ? null : webClientId,
      );

      // 2. Trigger Google Sign-In flow
      final googleUser = await googleSignIn.signIn();
      if (googleUser == null) {
        throw 'Sign in aborted by user.';
      }

      // 3. Obtain auth details (ID token and Access token)
      final googleAuth = await googleUser.authentication;
      final accessToken = googleAuth.accessToken;
      final idToken = googleAuth.idToken;

      if (idToken == null) {
        throw 'No ID Token found.';
      }

      // 4. Sign in to Supabase with Google credentials
      return await _supabase.auth.signInWithIdToken(
        provider: OAuthProvider.google,
        idToken: idToken,
        accessToken: accessToken,
      );
    } catch (e) {
      debugPrint('Error during Google Sign-In: $e');
      rethrow;
    }
  }

  /// Sign out
  Future<void> signOut() async {
    await _supabase.auth.signOut();
    final GoogleSignIn googleSignIn = GoogleSignIn();
    if (await googleSignIn.isSignedIn()) {
      await googleSignIn.signOut();
    }
  }
}
