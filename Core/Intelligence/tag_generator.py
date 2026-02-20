# tag_generator.py: tag_generator.py: Analytical tag generation for match insights.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Classes: TagGenerator

"""
Tag Generator Module
Generates analysis tags for team form, H2H, and standings analysis.
"""

from typing import List, Dict, Any, Tuple
from collections import Counter


class TagGenerator:
    """Generates various analysis tags for team and match analysis"""

    @staticmethod
    def check_threshold(count: int, total: int, rule_type: str) -> bool:
        """Check if count meets threshold criteria"""
        if total == 0:
            return False
        if rule_type == "majority":
            return count >= (total // 2 + 1)
        elif rule_type == "third":
            return count >= max(3, total // 3)
        elif rule_type == "quarter":
            return count >= max(2, total // 4)
        return False

    @staticmethod
    def classify_opponent_strength(rank: int, league_size: int) -> str:
        """Classify opponent strength based on league position"""
        if rank <= (league_size // 4):
            return 'top'
        elif rank <= (league_size // 2):
            return 'mid'
        else:
            return 'bottom'

    @staticmethod
    def _parse_match_result(match: Dict, team_name: str) -> Tuple[str, int, int, str]:
        """Parse match result for a specific team"""
        if not match:
            return "L", 0, 0, ""
        home = match.get("home", "")
        away = match.get("away", "")
        score = match.get("score", "0-0")
        winner = match.get("winner", "")
        try:
            gf, ga = map(int, score.replace(" ", "").split("-"))
        except:
            gf, ga = 0, 0

        if winner == "Draw":
            result = "D"
        elif (winner == "Home" and home == team_name) or (winner == "Away" and away == team_name):
            result = "W"
        else:
            result = "L"

        opponent = away if home == team_name else home
        return result, gf, ga, opponent

    @staticmethod
    def generate_form_tags(
        last_10_matches: List[Dict],
        team_name: str,
        standings: List[Dict]
    ) -> List[str]:
        """Generate form-based tags for team analysis"""
        matches = [m for m in last_10_matches if m]
        N = len(matches)
        if N < 3:
            return []

        team_to_rank = {t["team_name"]: t["position"] for t in standings}
        league_size = len(standings) or 20

        counts = {'SNG':0, 'CS':0, 'S1+':0, 'S2+':0, 'S3+':0,
                  'C1+':0, 'C2+':0, 'C3+':0, 'W':0, 'D':0, 'L':0}
        strength_counts = {'top': counts.copy(), 'mid': counts.copy(), 'bottom': counts.copy()}

        for match in matches:
            result, gf, ga, opponent = TagGenerator._parse_match_result(match, team_name)

            if gf == 0: counts['SNG'] += 1
            if ga == 0: counts['CS'] += 1
            if gf >= 1: counts['S1+'] += 1
            if gf >= 2: counts['S2+'] += 1
            if gf >= 3: counts['S3+'] += 1
            if ga >= 1: counts['C1+'] += 1
            if ga >= 2: counts['C2+'] += 1
            if ga >= 3: counts['C3+'] += 1
            if result == 'W': counts['W'] += 1
            if result == 'D': counts['D'] += 1
            if result == 'L': counts['L'] += 1

            if opponent in team_to_rank:
                strength = TagGenerator.classify_opponent_strength(team_to_rank[opponent], league_size)
                s = strength_counts[strength]
                if gf == 0: s['SNG'] += 1
                if ga == 0: s['CS'] += 1
                if gf >= 1: s['S1+'] += 1
                if gf >= 2: s['S2+'] += 1
                if gf >= 3: s['S3+'] += 1
                if ga >= 1: s['C1+'] += 1
                if ga >= 2: s['C2+'] += 1
                if ga >= 3: s['C3+'] += 1
                if result == 'W': s['W'] += 1
                if result == 'D': s['D'] += 1
                if result == 'L': s['L'] += 1

        tags = []
        team_slug = team_name.replace(" ", "_").upper()

        # Simplified tagging: majority → strong tag, third → normal tag (no "_third" suffix)
        for key, cnt in counts.items():
            if TagGenerator.check_threshold(cnt, N, "majority"):
                tags.append(f"{team_slug}_FORM_{key}")
            elif TagGenerator.check_threshold(cnt, N, "third"):
                tags.append(f"{team_slug}_FORM_{key}")

        for strength, s in strength_counts.items():
            s_N = sum(1 for m in matches
                      if (opp := TagGenerator._parse_match_result(m, team_name)[3]) in team_to_rank
                      and TagGenerator.classify_opponent_strength(team_to_rank[opp], league_size) == strength)
            if s_N < 2:
                continue
            for key, cnt in s.items():
                if TagGenerator.check_threshold(cnt, s_N, "third"):
                    tags.append(f"{team_slug}_FORM_{key}_vs_{strength.upper()}")

        return list(set(tags))

    @staticmethod
    def generate_h2h_tags(h2h_list: List[Dict], home_team: str, away_team: str) -> List[str]:
        """Generate head-to-head analysis tags"""
        matches = [m for m in h2h_list if m]
        if not matches:
            return []

        home_slug = home_team.replace(" ", "_").upper()
        away_slug = away_team.replace(" ", "_").upper()

        counts = {
            f'{home_slug}_WINS_H2H': 0,
            f'{away_slug}_WINS_H2H': 0,
            'H2H_D': 0,
            'H2H_O25': 0,
            'H2H_U25': 0,
            'H2H_BTTS': 0
        }

        for m in matches:
            try:
                hg, ag = map(int, m.get("score", "0-0").replace(" ", "").split("-"))
            except:
                continue
            total = hg + ag

            # Winner from perspective of current fixture teams
            if (m.get("winner") == "Home" and m.get("home") == home_team) or \
               (m.get("winner") == "Away" and m.get("away") == home_team):
                counts[f'{home_slug}_WINS_H2H'] += 1
            elif (m.get("winner") == "Home" and m.get("home") == away_team) or \
                 (m.get("winner") == "Away" and m.get("away") == away_team):
                counts[f'{away_slug}_WINS_H2H'] += 1
            else:
                counts['H2H_D'] += 1

            if total > 2:
                counts['H2H_O25'] += 1
            else:
                counts['H2H_U25'] += 1
            if hg > 0 and ag > 0:
                counts['H2H_BTTS'] += 1

        tags = []
        N = len(matches)
        for key, cnt in counts.items():
            if TagGenerator.check_threshold(cnt, N, "majority"):
                tags.append(key)
            elif TagGenerator.check_threshold(cnt, N, "third"):
                tags.append(f"{key}_third")

        return list(set(tags))

    @staticmethod
    def generate_standings_tags(standings: List[Dict], home_team: str, away_team: str) -> List[str]:
        """Generate league standings analysis tags"""
        if not standings:
            return []
        league_size = len(standings)
        rank = {t["team_name"]: t["position"] for t in standings}
        gd = {t["team_name"]: t.get("goal_difference", (t.get("goals_for") or 0) - (t.get("goals_against") or 0)) for t in standings}

        hr = rank.get(home_team, 999)
        ar = rank.get(away_team, 999)
        hgd = gd.get(home_team, 0)
        agd = gd.get(away_team, 0)

        home_slug = home_team.replace(" ", "_").upper()
        away_slug = away_team.replace(" ", "_").upper()

        tags = []
        if hr <= 3: tags.append(f"{home_slug}_TOP3")
        if hr > league_size - 5: tags.append(f"{home_slug}_BOTTOM5")
        if ar <= 3: tags.append(f"{away_slug}_TOP3")
        if ar > league_size - 5: tags.append(f"{away_slug}_BOTTOM5")
        if hgd > 0: tags.append(f"{home_slug}_GD_POS")
        if hgd < 0: tags.append(f"{home_slug}_GD_NEG")
        if agd > 0: tags.append(f"{away_slug}_GD_POS")
        if agd < 0: tags.append(f"{away_slug}_GD_NEG")
        if hr < ar - 8: tags.append(f"{home_slug}_TABLE_ADV8+")
        if ar < hr - 8: tags.append(f"{away_slug}_TABLE_ADV8+")
        if hgd > 10: tags.append(f"{home_slug}_GD_POS_STRONG")
        if hgd < -10: tags.append(f"{home_slug}_GD_NEG_WEAK")
        if agd > 10: tags.append(f"{away_slug}_GD_POS_STRONG")
        if agd < -10: tags.append(f"{away_slug}_GD_NEG_WEAK")
        return list(set(tags))
