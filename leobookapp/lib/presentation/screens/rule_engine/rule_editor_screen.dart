// rule_editor_screen.dart: rule_editor_screen.dart: Widget/screen for App — Rule Engine Screens.
// Part of LeoBook App — Rule Engine Screens
//
// Classes: RuleEditorScreen, _RuleEditorScreenState

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:leobookapp/data/models/rule_config_model.dart';
import 'package:leobookapp/data/services/leo_service.dart';
import 'package:leobookapp/logic/cubit/user_cubit.dart';

class RuleEditorScreen extends StatefulWidget {
  const RuleEditorScreen({super.key});

  @override
  State<RuleEditorScreen> createState() => _RuleEditorScreenState();
}

class _RuleEditorScreenState extends State<RuleEditorScreen> {
  late RuleConfigModel _config;
  bool _isSaving = false;

  @override
  void initState() {
    super.initState();
    _config = RuleConfigModel(); // Load default or fetch existing
  }

  Future<void> _saveConfig() async {
    setState(() => _isSaving = true);
    // Simulate save delay
    await Future.delayed(const Duration(seconds: 1));

    try {
      // In a real app, we'd injecting LeoService, but for now we instantiate or use a singleton
      // For this demo, we'll just print
      debugPrint("Saving config: ${_config.toJson()}");
      await LeoService().saveRuleConfig(_config);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Rule Configuration Saved!')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('Error saving config: $e')));
      }
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final userState = context.watch<UserCubit>().state;
    final canEdit = userState.user.canCreateCustomRules;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Custom Rule Editor'),
        actions: [
          IconButton(
            icon: const Icon(Icons.save),
            onPressed: (canEdit && !_isSaving) ? _saveConfig : null,
          ),
        ],
      ),
      body: !canEdit
          ? const Center(
              child: Text("Upgrade to Lite/Pro to create custom rules."),
            )
          : ListView(
              padding: const EdgeInsets.all(16.0),
              children: [
                _buildHeader(),
                const Divider(),
                _buildSlider(
                  "xG Advantage Weight",
                  _config.xgAdvantage,
                  (v) => setState(() => _config.xgAdvantage = v),
                ),
                _buildSlider(
                  "H2H Home Win Weight",
                  _config.h2hHomeWin,
                  (v) => setState(() => _config.h2hHomeWin = v),
                ),
                _buildSlider(
                  "H2H Away Win Weight",
                  _config.h2hAwayWin,
                  (v) => setState(() => _config.h2hAwayWin = v),
                ),
                _buildSlider(
                  "Form: Scores 2+",
                  _config.xgDraw,
                  (v) => setState(() => _config.xgDraw = v),
                ), // Reusing xgDraw as example, should use actual fields
                // ... add other sliders ...
                const SizedBox(height: 20),
                _buildNumberInput(
                  "Lookback Days",
                  _config.h2hLookbackDays,
                  (v) => setState(() => _config.h2hLookbackDays = v),
                ),
              ],
            ),
    );
  }

  Widget _buildHeader() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          "Rule Configuration",
          style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 8),
        TextFormField(
          initialValue: _config.name,
          decoration: const InputDecoration(
            labelText: "Rule Name",
            border: OutlineInputBorder(),
          ),
          onChanged: (v) => _config.name = v,
        ),
        const SizedBox(height: 8),
        TextFormField(
          initialValue: _config.description,
          decoration: const InputDecoration(
            labelText: "Description",
            border: OutlineInputBorder(),
          ),
          onChanged: (v) => _config.description = v,
        ),
      ],
    );
  }

  Widget _buildSlider(String label, double value, Function(double) onChanged) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(label, style: const TextStyle(fontWeight: FontWeight.w500)),
            Text(value.toStringAsFixed(1)),
          ],
        ),
        Slider(
          value: value,
          min: 0,
          max: 10,
          divisions: 20,
          label: value.toStringAsFixed(1),
          onChanged: onChanged,
        ),
      ],
    );
  }

  Widget _buildNumberInput(String label, int value, Function(int) onChanged) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label),
        SizedBox(
          width: 100,
          child: TextFormField(
            initialValue: value.toString(),
            keyboardType: TextInputType.number,
            onChanged: (v) => onChanged(int.tryParse(v) ?? value),
            decoration: const InputDecoration(border: OutlineInputBorder()),
          ),
        ),
      ],
    );
  }
}
