import math

from src.constants.features import POS2CATEGORY


def get_pos_features():
    """Returns dict mapping each POS to its features and values."""
    result = {}
    for pos, category in POS2CATEGORY.items():
        if category is None:
            result[pos] = {}
        else:
            result[pos] = {
                feature.name: list(feature.values)
                for feature in category.features
            }
    return result


def get_weight_color(weight, max_weight=10):
    """Returns CSS color based on weight (green=0, red=max)."""
    if weight is None or (isinstance(weight, float) and math.isnan(weight)):
        weight = 0
    ratio = min(weight / max_weight, 1.0)
    r = int(40 + ratio * 180)
    g = int(167 - ratio * 114)
    return f'rgb({r},{g},69)'
