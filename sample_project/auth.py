def authenticate(username: str, password: str) -> dict | None:
    """Demo-only authentication. Never store plaintext passwords in production."""
    if not username or not password:
        return None
    if username == "student" and password == "demo":
        return {"username": username, "role": "student"}
    return None
