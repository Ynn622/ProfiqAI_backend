import numpy as np

def nan_to_none(obj):
    if isinstance(obj, float) and np.isnan(obj):
        return None
    if isinstance(obj, list):
        return [nan_to_none(i) for i in obj]
    if isinstance(obj, dict):
        return {k: nan_to_none(v) for k, v in obj.items()}
    return obj