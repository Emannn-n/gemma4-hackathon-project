from __future__ import annotations


def build_markdown_report(project_name: str, source_label: str, analysis: dict, summary: dict) -> str:
    lines = [f"# CodeMap Report: {project_name}", "", f"**Source:** {source_label}", "", "## Overview", summary["overview"], "", "## Project Structure", f"- Python files: {len(analysis['files'])}", f"- Detected functions: {analysis['totals']['functions']}", f"- Detected classes: {analysis['totals']['classes']}", f"- Detected module links: {len(analysis['graph_edges'])}", "", "## Challenge Radar"]
    if not analysis["findings"]:
        lines.append("No checks were triggered. This does not prove that the project has no issues.")
    for finding in analysis["findings"]:
        lines.extend([f"### [{finding['severity']}] {finding['title']}", finding["description"], f"- Evidence: {finding['evidence']}", f"- Suggested next step: {finding['recommendation']}", ""])
    lines.extend(["## Readiness Checklist", ""])
    for check in analysis["readiness"]:
        lines.append(f"- **{check['status']} — {check['title']}:** {check['detail']}")
    lines.extend(["", "## Possible First Contribution Points", ""])
    for candidate in analysis["contribution_candidates"][:8]:
        lines.append(f"- **{candidate['path']}** — {candidate['reason']} Suggested starter task: {candidate['task']}")
    lines.extend(["", "## Limitations", "- This report uses static analysis and a limited set of repository files.", "- It does not run the project, execute tests, or guarantee security.", "- AI-generated recommendations should be verified by a developer.", ""])
    return "\n".join(lines)
