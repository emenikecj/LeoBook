// realtime_manager.dart: Centralized Supabase Broadcast Realtime subscription manager.
// Part of LeoBook App — Data Layer
//
// Classes: RealtimeManager

import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

/// Callback type for realtime broadcast events.
typedef RealtimeHandler = void Function(Map<String, dynamic> payload);

/// Manages private broadcast channel subscriptions to all Supabase tables.
///
/// Subscribes to topics matching table names (e.g., 'predictions', 'schedules').
/// Requires broadcast triggers to be set up on the Supabase side and
/// realtime.messages RLS policies for auth access.
class RealtimeManager {
  final SupabaseClient _supabase;
  final Map<String, RealtimeChannel> _channels = {};
  final Map<String, List<RealtimeHandler>> _handlers = {};

  RealtimeManager(this._supabase);

  /// Subscribe to broadcast events for a table topic.
  /// The topic name must match what the Postgres trigger broadcasts to.
  Future<void> subscribeToTable(String table) async {
    if (_channels.containsKey(table)) return; // Already subscribed

    final channel = _supabase.channel(
      table,
      opts: const RealtimeChannelConfig(private: true),
    );

    // Listen to all broadcast events (INSERT, UPDATE, DELETE)
    channel.onBroadcast(
      event: '*',
      callback: (payload) {
        final data = Map<String, dynamic>.from(payload);
        _dispatch(table, data);
      },
    );

    channel.subscribe();
    _channels[table] = channel;
    debugPrint('[RealtimeManager] Subscribed to broadcast topic: $table');
  }

  /// Unsubscribe and remove a table topic.
  Future<void> unsubscribeTable(String table) async {
    final channel = _channels.remove(table);
    if (channel != null) {
      await _supabase.removeChannel(channel);
      debugPrint('[RealtimeManager] Unsubscribed from topic: $table');
    }
    _handlers.remove(table);
  }

  /// Add a handler for events on a specific table topic.
  void addHandler(String table, RealtimeHandler handler) {
    _handlers.putIfAbsent(table, () => []).add(handler);
  }

  /// Remove a specific handler for a table topic.
  void removeHandler(String table, RealtimeHandler handler) {
    final list = _handlers[table];
    list?.remove(handler);
    if (list != null && list.isEmpty) _handlers.remove(table);
  }

  void _dispatch(String table, Map<String, dynamic> payload) {
    final list = _handlers[table];
    if (list == null) return;
    for (final h in list) {
      try {
        h(payload);
      } catch (e, st) {
        debugPrint('[RealtimeManager] Handler error for $table: $e\n$st');
      }
    }
  }

  /// Clean up all channels and handlers.
  Future<void> dispose() async {
    for (final ch in _channels.values) {
      try {
        await _supabase.removeChannel(ch);
      } catch (e) {
        debugPrint('[RealtimeManager] Error removing channel: $e');
      }
    }
    _channels.clear();
    _handlers.clear();
    debugPrint('[RealtimeManager] Disposed all channels');
  }
}
