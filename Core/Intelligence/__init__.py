"""
Intelligence Package: Advanced AI Engine for Football Prediction & Analysis
Refactored for Clean Architecture (v2.7)

This package contains the core intelligence components for LeoBook:
- Learning Engine: Adaptive rule weight management
- ML Model: Machine learning prediction ensemble
- Rule Engine: Comprehensive rule-based prediction logic
- Selector Manager: CSS selector storage and auto-healing
- Visual Analyzer: Screenshot analysis and Leo AI vision
- Popup Handler: Universal popup dismissal and UI recovery
- Page Analyzer: Webpage content analysis and data extraction
- Betting Markets: Market-specific math and probability
"""

from .rule_engine import RuleEngine
from .selector_manager import SelectorManager
from .visual_analyzer import VisualAnalyzer
from .popup_handler import PopupHandler
from .page_analyzer import PageAnalyzer

__version__ = "2.6.0"
__all__ = [
    "RuleEngine",
    "SelectorManager",
    "VisualAnalyzer",
    "PopupHandler",
    "PageAnalyzer"
]
