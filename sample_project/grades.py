def calculate_grade(scores: list[float]) -> float:
    if not scores:
        return 0.0
    if any(score < 0 or score > 100 for score in scores):
        raise ValueError("Scores must be between 0 and 100")
    total = 0.0
    for score in scores:
        total += score
    return total / len(scores)
