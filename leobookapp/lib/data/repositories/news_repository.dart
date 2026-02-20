// news_repository.dart: news_repository.dart: Widget/screen for App — Repositories.
// Part of LeoBook App — Repositories
//
// Classes: NewsRepository

import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:leobookapp/data/models/news_model.dart';

class NewsRepository {
  final SupabaseClient _supabase = Supabase.instance.client;

  Future<List<NewsModel>> fetchNews() async {
    try {
      final response = await _supabase
          .from('news')
          .select()
          .order('published_at', ascending: false)
          .limit(10);

      return (response as List)
          .map((json) => NewsModel.fromJson(json))
          .toList();
    } catch (e) {
      // Fallback or empty list on error
      return [];
    }
  }
}
