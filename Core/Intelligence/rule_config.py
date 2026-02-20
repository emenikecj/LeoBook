# rule_config.py: rule_config.py: Configuration object for custom prediction rules.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Classes: RuleConfig

from dataclasses import dataclass, field
from typing import Dict

@dataclass
class RuleConfig:
    name: str = "Default"
    description: str = "Standard LeoBook prediction logic"
    
    # Weightings (0-10 scale usually)
    xg_advantage: float = 3.0
    xg_draw: float = 2.0
    
    h2h_home_win: float = 3.0
    h2h_away_win: float = 3.0
    h2h_draw: float = 4.0
    h2h_over25: float = 3.0
    
    standings_top_vs_bottom: float = 6.0
    standings_table_advantage: float = 3.0
    standings_gd_strong: float = 2.0
    standings_gd_weak: float = 2.0
    
    form_score_2plus: float = 4.0
    form_score_3plus: float = 2.0
    form_concede_2plus: float = 4.0
    form_no_score: float = 5.0
    form_clean_sheet: float = 5.0
    form_vs_top_win: float = 3.0
    
    # Parameters
    h2h_lookback_days: int = 540
    min_h2h_games: int = 0
    
    def to_dict(self) -> Dict:
        return self.__dict__

    @staticmethod
    def from_dict(data: Dict) -> 'RuleConfig':
        return RuleConfig(**data)
