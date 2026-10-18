from __future__ import annotations

import io
import re
import zipfile
from pathlib import PurePosixPath
from urllib.parse import urlparse

import requests

MAX_FILES = 120
MAX_FILE_BYTES = 180_000
MAX_TOTAL_BYTES = 1_500_000
ALLOWED_SUFFIXES = {".py", ".md", ".toml", ".txt", ".yml", ".yaml", ".json", ".cfg", ".ini"}
SKIP_PARTS = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build", ".idea", ".vscode", "site-packages", "vendor"}

class GitHubLoadError(Exception):
    pass


def _is_allowed(path: str) -> bool:
    p = PurePosixPath(path)
    if p.is_absolute() or ".." in p.parts or any(part.lower() in SKIP_PARTS for part in p.parts):
        return False
    if p.name.startswith(".") and p.name.lower() not in {".gitignore"}:
        return False
    if p.suffix.lower() not in ALLOWED_SUFFIXES and p.name.lower() not in {"readme", "dockerfile", "makefile", ".gitignore"}:
        return False
    if any(word in p.name.lower() for word in ("secret", "credential", "private_key")) or p.name.lower() == ".env":
        return False
    return True


def _decode_text(raw: bytes) -> str | None:
    if len(raw) > MAX_FILE_BYTES or b"\x00" in raw:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def load_github_repository(url: str) -> tuple[str, dict[str, str], str]:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        raise GitHubLoadError("Please use a public repository URL from https://github.com/owner/repository.")
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 2 or not re.fullmatch(r"[A-Za-z0-9_.-]+", parts[0]) or not re.fullmatch(r"[A-Za-z0-9_.-]+", parts[1]):
        raise GitHubLoadError("That URL doesn't look like a repository URL. Use https://github.com/owner/repository.")
    owner, repo = parts[0], parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    base = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "CodeMap-Hackathon-MVP"}
    try:
        response = requests.get(base, headers=headers, timeout=12)
        if response.status_code == 404:
            raise GitHubLoadError("Repository not found or not public. Check the URL and try a public repository.")
        if response.status_code == 403:
            raise GitHubLoadError("GitHub rate limit reached. Try again shortly or upload the repository as a ZIP.")
        response.raise_for_status()
        metadata = response.json()
        branch = metadata.get("default_branch") or "main"
        tree_response = requests.get(f"{base}/git/trees/{branch}?recursive=1", headers=headers, timeout=20)
        tree_response.raise_for_status()
        tree = tree_response.json().get("tree", [])
        candidates = [item for item in tree if item.get("type") == "blob" and _is_allowed(item.get("path", "")) and item.get("size", 0) <= MAX_FILE_BYTES]
        candidates.sort(key=lambda x: (0 if x["path"].endswith(".py") else 1, x["path"].lower()))
        candidates = candidates[:MAX_FILES]
        files: dict[str, str] = {}
        total = 0
        for item in candidates:
            if total >= MAX_TOTAL_BYTES:
                break
            file_response = requests.get(item["url"], headers=headers, timeout=12)
            if not file_response.ok:
                continue
            payload = file_response.json()
            if payload.get("encoding") != "base64":
                continue
            import base64
            raw = base64.b64decode(payload.get("content", ""))
            text = _decode_text(raw)
            if text is None:
                continue
            files[item["path"]] = text
            total += len(raw)
        if not files:
            raise GitHubLoadError("No supported readable files were found. Try a small Python repository or upload a ZIP.")
        return metadata.get("name", repo), files, f"GitHub: {owner}/{repo} (branch: {branch})"
    except GitHubLoadError:
        raise
    except requests.RequestException as exc:
        raise GitHubLoadError(f"Couldn't fetch this repository from GitHub: {exc}. You can try uploading a ZIP instead.") from exc
    except (ValueError, KeyError) as exc:
        raise GitHubLoadError("GitHub returned an unexpected response. Try uploading the repository as a ZIP.") from exc


def load_zip_project(data: bytes, filename: str) -> tuple[str, dict[str, str]]:
    if len(data) > 12_000_000:
        raise GitHubLoadError("ZIP is larger than the 12 MB MVP limit. Try a smaller source-only ZIP.")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise GitHubLoadError("That file isn't a valid ZIP archive.") from exc
    files: dict[str, str] = {}
    total = 0
    for info in archive.infolist():
        path = info.filename.replace("\\", "/")
        if info.is_dir() or not _is_allowed(path) or info.file_size > MAX_FILE_BYTES:
            continue
        # Avoid suspicious compression ratios and never extract to disk.
        if info.compress_size and info.file_size / info.compress_size > 200:
            continue
        if len(files) >= MAX_FILES or total >= MAX_TOTAL_BYTES:
            break
        try:
            raw = archive.read(info)
        except (OSError, RuntimeError, zipfile.BadZipFile):
            continue
        text = _decode_text(raw)
        if text is None:
            continue
        files[path] = text
        total += len(raw)
    if not files:
        raise GitHubLoadError("No supported readable source or documentation files were found in this ZIP.")
    root_name = PurePosixPath(filename).stem or "Uploaded project"
    return root_name, files
