"""
Feature Extraction Package for Person Re-Identification
Provides advanced feature extractors for robust person matching
"""

from .clothing_analyzer import ClothingAnalyzer
from .osnet_extractor import DummyOSNetExtractor, OSNetExtractor, create_osnet_extractor

__all__ = [
    "ClothingAnalyzer",
    "OSNetExtractor",
    "DummyOSNetExtractor",
    "create_osnet_extractor",
]

__version__ = "1.0.0"
