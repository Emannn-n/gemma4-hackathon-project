from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()

class ModelConfigurationError(Exception):
    pass

class ModelRequestError(Exception):
    pass


class GemmaService:
    """Model adapter. Supports Google's Gemini API or an OpenAI-compatible Flow endpoint.

    If the event's Flow environment uses an OpenAI-compatible endpoint, set
    GEMMA_API_BASE_URL and GEMMA_API_KEY in .env. Otherwise the Google GenAI SDK
    uses GEMMA_API_KEY as the Google AI Studio API key.
    """
    def __init__(self) -> None:
        self.api_key = os.getenv("GEMMA_API_KEY", "").strip()
        self.model = os.getenv("GEMMA_MODEL", "gemma-4-26b-a4b-it").strip()
        self.base_url = os.getenv("GEMMA_API_BASE_URL", "").strip()
        if not self.api_key:
            raise ModelConfigurationError(
                "Gemma 4 isn't configured yet. Copy .env.example to .env and add the API key provided by your event's Flow setup. Do not share the key publicly."
            )

    def _generate(self, prompt: str, system: str = "You are CodeMap, a careful software analysis assistant.") -> str:
        try:
            if self.base_url:
                from openai import OpenAI
                client = OpenAI(api_key=self.api_key, base_url=self.base_url)
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                    temperature=0.2,
                    max_tokens=1400,
                )
                result = response.choices[0].message.content
            else:
                from google import genai
                client = genai.Client(api_key=self.api_key)
                response = client.models.generate_content(
                    model=self.model,
                    contents=f"{system}\n\n{prompt}",
                )
                result = response.text
            if not result or not result.strip():
                raise ModelRequestError("Gemma 4 returned an empty response. Try again with a smaller question or project.")
            return result.strip()
        except ModelRequestError:
            raise
        except Exception as exc:
            message = str(exc)
            if "401" in message or "403" in message or "API key" in message.lower() or "unauthorized" in message.lower():
                raise ModelRequestError("The model provider rejected the key or access. Check your event-provided API key, endpoint, and model ID in .env.") from exc
            raise ModelRequestError(f"Gemma 4 request failed: {message[:400]}") from exc

    @staticmethod
    def _context(project_name: str, analysis: dict[str, Any]) -> str:
        compact = {
            "project": project_name,
            "python_files": [{"path": f["path"], "imports": f["imports"], "functions": f["functions"][:30], "classes": f["classes"][:20], "syntax_error": f["syntax_error"]} for f in analysis["files"][:50]],
            "entry_points": analysis["entry_points"],
            "static_findings": analysis["findings"][:30],
            "external_imports": analysis["external_imports"][:30],
            "limits": "Static analysis only. File content may be incomplete. Do not claim tests were run. Mark uncertain conclusions as hypotheses."
        }
        return json.dumps(compact, ensure_ascii=False)

    def review_challenges(self, project_name: str, analysis: dict[str, Any]) -> str:
        return self._generate("Review this static project analysis. Prioritize up to 5 actionable challenges. For each include severity, evidence path/line if available, why it matters, and next step. Separate confirmed static signals from hypotheses; never claim a vulnerability is confirmed without evidence.\n\n" + self._context(project_name, analysis))

    def contribution_plan(self, project_name: str, analysis: dict[str, Any], role: str) -> str:
        return self._generate(f"Create a first-contribution plan for a {role.lower()} working on {project_name}. Suggest up to 3 small tasks based only on the supplied evidence. For each include target file, prerequisite knowledge, exact first step, and how to validate it. Do not invent repository issues or functions.\n\n" + self._context(project_name, analysis))

    def trace_journey(self, project_name: str, question: str, analysis: dict[str, Any], files: dict[str, str]) -> str:
        context = self._context(project_name, analysis)
        # Include a bounded set of relevant source files; avoid shipping the full repository.
        snippets = []
        q_words = {w.lower() for w in question.replace("?", " ").replace(".", " ").split() if len(w) > 3}
        ordered = sorted(files.items(), key=lambda kv: (0 if any(w in kv[0].lower() for w in q_words) else 1, 0 if kv[0].endswith(".py") else 2))
        for path, content in ordered[:5]:
            snippets.append(f"FILE: {path}\n{content[:5000]}")
        return self._generate(f"Question: {question}\nExplain the likely execution path step by step. Cite file names and function names from the context. Distinguish detected links from inferred links, and explicitly say when the code is insufficient to prove a path.\n\nSTRUCTURE:\n{context}\n\nSOURCE SNIPPETS:\n" + "\n\n".join(snippets))

    def role_guide(self, project_name: str, analysis: dict[str, Any], role: str, goal: str) -> str:
        return self._generate(f"Project: {project_name}\nUser mode: {role}\nTask: {goal}\nUse only supplied evidence, and label uncertainty.\n\n" + self._context(project_name, analysis))

    def executive_summary(self, project_name: str, analysis: dict[str, Any]) -> str:
        return self._generate("Write a concise executive summary with project structure, strongest evidence-backed findings, and 3 prioritized next actions. Do not assign an arbitrary overall quality score.\n\n" + self._context(project_name, analysis))

    def explain_file(self, path: str, content: str, role: str) -> str:
        return self._generate(f"Explain the following source file for a {role.lower()}. Cover purpose, important functions/classes, inputs/outputs, dependencies, and anything uncertain. Use only code evidence.\n\nFILE: {path}\n```python\n{content[:12000]}\n``` ")
