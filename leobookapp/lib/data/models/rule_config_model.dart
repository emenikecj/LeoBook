// rule_config_model.dart: rule_config_model.dart: Widget/screen for App — Data Models.
// Part of LeoBook App — Data Models
//
// Classes: RuleConfigModel

class RuleConfigModel {
  String name;
  String description;
  double xgAdvantage;
  double xgDraw;
  double h2hHomeWin;
  double h2hAwayWin;
  double h2hDraw;
  double h2hOver25;
  double standingsTopBottom;
  double standingsTableAdv;
  int h2hLookbackDays;

  RuleConfigModel({
    this.name = "Custom Rule",
    this.description = "My custom prediction strategy",
    this.xgAdvantage = 3.0,
    this.xgDraw = 2.0,
    this.h2hHomeWin = 3.0,
    this.h2hAwayWin = 3.0,
    this.h2hDraw = 4.0,
    this.h2hOver25 = 3.0,
    this.standingsTopBottom = 6.0,
    this.standingsTableAdv = 3.0,
    this.h2hLookbackDays = 540,
  });

  Map<String, dynamic> toJson() {
    return {
      'name': name,
      'description': description,
      'xg_advantage': xgAdvantage,
      'xg_draw': xgDraw,
      'h2h_home_win': h2hHomeWin,
      'h2h_away_win': h2hAwayWin,
      'h2h_draw': h2hDraw,
      'h2h_over25': h2hOver25,
      'standings_top_vs_bottom': standingsTopBottom,
      'standings_table_advantage': standingsTableAdv,
      'h2h_lookback_days': h2hLookbackDays,
    };
  }

  factory RuleConfigModel.fromJson(Map<String, dynamic> json) {
    return RuleConfigModel(
      name: json['name'] ?? "Custom Rule",
      description: json['description'] ?? "",
      xgAdvantage: (json['xg_advantage'] ?? 3.0).toDouble(),
      xgDraw: (json['xg_draw'] ?? 2.0).toDouble(),
      h2hHomeWin: (json['h2h_home_win'] ?? 3.0).toDouble(),
      h2hAwayWin: (json['h2h_away_win'] ?? 3.0).toDouble(),
      h2hDraw: (json['h2h_draw'] ?? 4.0).toDouble(),
      h2hOver25: (json['h2h_over25'] ?? 3.0).toDouble(),
      standingsTopBottom: (json['standings_top_vs_bottom'] ?? 6.0).toDouble(),
      standingsTableAdv: (json['standings_table_advantage'] ?? 3.0).toDouble(),
      h2hLookbackDays: json['h2h_lookback_days'] ?? 540,
    );
  }
}
