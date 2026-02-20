# model.py: model.py: Module for Core — Intelligence (AI Engine).
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Functions: analyze_match(), update_learning_weights(), train_ml_models(), analyze()

"""
LeoBook AI Model Engine
Main entry point for prediction analysis combining Learning, ML, and Rule-based approaches.
"""

# Import all components for unified interface
from .learning_engine import LearningEngine
from .ml_model import MLModel
from .rule_engine import RuleEngine

def analyze_match(vision_data):
    """
    Main prediction analysis function - unified interface to all AI components.

    Args:
        vision_data: Dictionary containing match data (teams, forms, standings, H2H)

    Returns:
        Dictionary with prediction results and analysis
    """
    return RuleEngine.analyze(vision_data)

def update_learning_weights():
    """
    Update learning weights based on prediction performance.

    Returns:
        Updated weights dictionary
    """
    return LearningEngine.update_weights()

def train_ml_models():
    """
    Train machine learning models with historical data.

    Returns:
        Boolean indicating success
    """
    return MLModel.train_models()

# Legacy compatibility - maintain old function names
def analyze(vision_data):
    """Legacy function - use analyze_match instead"""
    return analyze_match(vision_data)
