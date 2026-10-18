from auth import authenticate
from grades import calculate_grade


def login(username: str, password: str) -> dict:
    user = authenticate(username, password)
    if not user:
        return {"ok": False, "message": "Invalid credentials"}
    return {"ok": True, "user": user}


def student_result(scores: list[float]) -> dict:
    grade = calculate_grade(scores)
    return {"grade": grade, "passed": grade >= 50}
