from typing import Any, Dict, List


def split_scores_by_sign(data: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    將以 `_Score` 結尾的欄位依分數正負分類，並由高到低排序。

    Returns:
        {"positive": [...], "negative": [...]}
    """
    positive_scores: List[tuple[str, float]] = []
    negative_scores: List[tuple[str, float]] = []

    for key, value in data.items():
        if not key.endswith("_Score"):
            continue
        if value is None:
            continue
        try:
            score = float(value)
        except (TypeError, ValueError):
            continue
        if score > 0:
            positive_scores.append((key, score))
        elif score < 0:
            negative_scores.append((key, score))

    def _strip_suffix(name: str) -> str:
        return name[:-6] if name.endswith("_Score") else name

    positive_sorted = [
        _strip_suffix(key) for key, _ in sorted(positive_scores, key=lambda item: item[1], reverse=True)
    ]
    negative_sorted = [
        _strip_suffix(key) for key, _ in sorted(negative_scores, key=lambda item: item[1], reverse=True)
    ]

    return {"positive": positive_sorted, "negative": negative_sorted}
