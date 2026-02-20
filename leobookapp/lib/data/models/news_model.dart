// news_model.dart: news_model.dart: Widget/screen for App — Data Models.
// Part of LeoBook App — Data Models
//
// Classes: NewsModel

class NewsModel {
  final String id;
  final String title;
  final String imageUrl;
  final String source; // e.g., "Sky Sports", "BBC"
  final String timeAgo; // e.g., "2h ago"
  final String url;

  NewsModel({
    required this.id,
    required this.title,
    required this.imageUrl,
    required this.source,
    required this.timeAgo,
    required this.url,
  });

  factory NewsModel.fromJson(Map<String, dynamic> json) {
    return NewsModel(
      id: (json['id'] ?? '').toString(),
      title: json['title'] ?? '',
      imageUrl: json['image_url'] ?? '',
      source: json['source'] ?? '',
      timeAgo: json['published_at'] != null
          ? _formatTimeAgo(DateTime.parse(json['published_at']))
          : 'recent',
      url: json['url'] ?? '',
    );
  }

  static String _formatTimeAgo(DateTime dateTime) {
    final duration = DateTime.now().difference(dateTime);
    if (duration.inDays > 0) return '${duration.inDays}d ago';
    if (duration.inHours > 0) return '${duration.inHours}h ago';
    if (duration.inMinutes > 0) return '${duration.inMinutes}m ago';
    return 'just now';
  }
}
