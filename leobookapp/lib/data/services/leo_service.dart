// leo_service.dart: leo_service.dart: Widget/screen for App — Services.
// Part of LeoBook App — Services
//
// Classes: LeoService

import 'dart:convert';
import 'dart:io';
import '../models/rule_config_model.dart';

class LeoService {
  // Hardcoded for this environment as per user instructions
  static const String _storePath =
      r'C:\Users\Admin\Desktop\ProProjection\LeoBook\Data\Store';

  Future<void> saveRuleConfig(RuleConfigModel config) async {
    final file = File('$_storePath\\rule_config.json');
    await file.writeAsString(jsonEncode(config.toJson()));
  }

  Future<RuleConfigModel> loadRuleConfig() async {
    final file = File('$_storePath\\rule_config.json');
    if (await file.exists()) {
      final jsonString = await file.readAsString();
      return RuleConfigModel.fromJson(jsonDecode(jsonString));
    }
    return RuleConfigModel(); // Default
  }

  Future<void> triggerBacktest(RuleConfigModel config) async {
    // 1. Save config first
    await saveRuleConfig(config);

    // 2. Create trigger file
    final triggerFile = File('$_storePath\\trigger_backtest.json');
    await triggerFile.writeAsString(
      jsonEncode({
        'timestamp': DateTime.now().toIso8601String(),
        'config_name': config.name,
      }),
    );
  }

  // Method to check for results
  Future<List<Map<String, dynamic>>> getBacktestResults(
    String configName,
  ) async {
    final file = File(
      '$_storePath\\predictions_custom_$configName.csv',
    ); // This assumes CSV format
    if (!await file.exists()) return [];

    final lines = await file.readAsLines();
    if (lines.isEmpty) return [];

    final headers = lines.first.split(',');
    final List<Map<String, dynamic>> results = [];

    for (var i = 1; i < lines.length; i++) {
      final values = lines[i].split(',');
      final Map<String, dynamic> row = {};
      for (var j = 0; j < headers.length; j++) {
        if (j < values.length) {
          row[headers[j]] = values[j];
        }
      }
      results.add(row);
    }
    return results;
  }
}
