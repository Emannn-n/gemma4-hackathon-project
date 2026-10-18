from __future__ import annotations

import streamlit as st

from code_analyzer import analyze_project, build_graphviz, create_project_report
from gemma_service import GemmaService, ModelConfigurationError, ModelRequestError
from github_loader import GitHubLoadError, load_github_repository, load_zip_project
from report_builder import build_markdown_report

st.set_page_config(page_title="CodeMap · Project Intelligence", page_icon="🗺️", layout="wide")

st.markdown("""
<style>
:root { --cm-accent: #a78bfa; }
.block-container { padding-top: 1.5rem; max-width: 1500px; }
.hero { padding: 1.5rem 1.7rem; border-radius: 18px; background: linear-gradient(120deg, rgba(124,58,237,.20), rgba(14,165,233,.09)); border: 1px solid rgba(167,139,250,.35); margin-bottom: 1rem; }
.hero h1 { margin: 0; letter-spacing: -1px; }
.hero p { color: #9ca3af; margin-bottom: 0; }
.small-muted { color: #9ca3af; font-size: .9rem; }
.finding { padding: .9rem 1rem; border: 1px solid rgba(148,163,184,.25); border-radius: 12px; margin: .55rem 0; }
</style>
<div class="hero">
  <h1>🗺️ CodeMap</h1>
  <p>Understand the code. Find the challenges. Discover what to improve next.</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("Workspace")
    source = st.radio("Project source", ["Public GitHub repository", "Upload ZIP"], index=0)
    role = st.selectbox("I'm using CodeMap as…", ["Developer", "Student", "Teacher"])
    st.caption("CodeMap analyzes Python repositories in this MVP. Only public GitHub repositories are supported.")
    st.divider()
    st.caption("Gemma 4 powers explanations. Static checks are performed locally where possible.")

project_files: dict[str, str] = {}
project_name = ""
source_label = ""
load_error = None

if source == "Public GitHub repository":
    repo_url = st.text_input("GitHub repository URL", placeholder="https://github.com/owner/repository")
    if st.button("Analyze repository", type="primary", use_container_width=True):
        if not repo_url.strip():
            st.warning("Enter a public GitHub repository URL first.")
        else:
            with st.spinner("Fetching repository files…"):
                try:
                    project_name, project_files, source_label = load_github_repository(repo_url.strip())
                    st.session_state["project_name"] = project_name
                    st.session_state["project_files"] = project_files
                    st.session_state["source_label"] = source_label
                except GitHubLoadError as exc:
                    st.error(str(exc))
else:
    zip_file = st.file_uploader("Upload a project ZIP", type=["zip"])
    if st.button("Analyze uploaded project", type="primary", use_container_width=True):
        if zip_file is None:
            st.warning("Choose a ZIP file first.")
        else:
            with st.spinner("Reading project files…"):
                try:
                    project_name, project_files = load_zip_project(zip_file.getvalue(), zip_file.name)
                    source_label = f"Uploaded ZIP: {zip_file.name}"
                    st.session_state["project_name"] = project_name
                    st.session_state["project_files"] = project_files
                    st.session_state["source_label"] = source_label
                except GitHubLoadError as exc:
                    st.error(str(exc))

project_name = st.session_state.get("project_name", project_name)
project_files = st.session_state.get("project_files", project_files)
source_label = st.session_state.get("source_label", source_label)

if not project_files:
    st.info("**Start here:** paste a public GitHub URL or upload a ZIP. For a quick first test, try a small Python project with a few `.py` files.")
    st.stop()

analysis = analyze_project(project_files)
summary = create_project_report(project_name, analysis, source_label)

metric_cols = st.columns(4)
metric_cols[0].metric("Python files", len(analysis["files"]))
metric_cols[1].metric("Functions", analysis["totals"]["functions"])
metric_cols[2].metric("Classes", analysis["totals"]["classes"])
metric_cols[3].metric("Static signals", len(analysis["findings"]))

st.caption(f"Source: {source_label} · Analyzed {len(project_files)} readable source/documentation files. Results are an aid to review, not a guarantee of correctness or security.")

tabs = st.tabs(["Overview & Map", "Challenge Radar", "First Contribution", "Trace the Journey", "Learning / Teaching", "Readiness & Export", "File Explorer"])

with tabs[0]:
    left, right = st.columns([1.5, 1])
    with left:
        st.subheader("How the project is connected")
        dot = build_graphviz(analysis)
        if dot:
            st.graphviz_chart(dot, use_container_width=True)
        else:
            st.info("No Python module connections were detected yet. The file explorer still lists available files.")
    with right:
        st.subheader("Project snapshot")
        st.write(summary["overview"])
        st.markdown("**Likely entry points**")
        if analysis["entry_points"]:
            for path in analysis["entry_points"]:
                st.code(path, language="text")
        else:
            st.write("No obvious entry point detected. Check README instructions or identify the command used to start the app.")
        st.markdown("**Detected dependencies**")
        st.write(", ".join(analysis["external_imports"][:20]) or "No external imports detected.")

with tabs[1]:
    st.subheader("Project Challenge Radar")
    st.caption("These are signals found by simple checks, not proof that the project is broken. AI explanations are separate from static findings.")
    if not analysis["findings"]:
        st.success("No checks were triggered. This does not mean the project has no issues.")
    for finding in analysis["findings"]:
        with st.container(border=True):
            st.markdown(f"**{finding['title']}**  ·  `{finding['severity']}`")
            st.write(finding["description"])
            st.caption(f"Evidence: {finding['evidence']}")
            st.write(f"Suggested next step: {finding['recommendation']}")
    if st.button("Ask Gemma 4 to review project challenges", key="challenge_ai"):
        with st.spinner("Asking Gemma 4 to review the detected signals…"):
            try:
                st.session_state["challenge_review"] = GemmaService().review_challenges(project_name, analysis)
            except (ModelConfigurationError, ModelRequestError) as exc:
                st.error(str(exc))
    if st.session_state.get("challenge_review"):
        st.markdown("#### Gemma 4 review")
        st.markdown(st.session_state["challenge_review"])

with tabs[2]:
    st.subheader("Find a good first contribution")
    st.write("CodeMap prioritizes small, understandable starting points using available code structure. Suggestions are starting hypotheses; verify them before changing a project.")
    candidates = analysis["contribution_candidates"]
    if candidates:
        for item in candidates[:8]:
            with st.container(border=True):
                st.markdown(f"**{item['path']}**")
                st.write(item["reason"])
                st.caption(f"Possible starter task: {item['task']}")
    else:
        st.info("No obvious beginner-sized candidates were found. Explore a small function in the file explorer instead.")
    if st.button("Generate a beginner contribution plan with Gemma 4", key="contrib_ai"):
        with st.spinner("Preparing contribution plan…"):
            try:
                st.session_state["contribution_plan"] = GemmaService().contribution_plan(project_name, analysis, role)
            except (ModelConfigurationError, ModelRequestError) as exc:
                st.error(str(exc))
    if st.session_state.get("contribution_plan"):
        st.markdown("#### Suggested contribution plan")
        st.markdown(st.session_state["contribution_plan"])

with tabs[3]:
    st.subheader("Trace the Journey")
    st.write("Ask how a user action or program flow moves through the code. CodeMap supplies detected files and function names as context; the model must flag uncertainty.")
    journey_question = st.text_input("What journey should we trace?", placeholder="What happens when a user logs in?")
    if st.button("Trace journey with Gemma 4", type="primary", key="trace"):
        if not journey_question.strip():
            st.warning("Enter a question about the project flow.")
        else:
            with st.spinner("Tracing relevant code…"):
                try:
                    st.session_state["journey_answer"] = GemmaService().trace_journey(project_name, journey_question, analysis, project_files)
                except (ModelConfigurationError, ModelRequestError) as exc:
                    st.error(str(exc))
    if st.session_state.get("journey_answer"):
        st.markdown(st.session_state["journey_answer"])

with tabs[4]:
    st.subheader({"Student": "Learn this codebase", "Teacher": "Create a project review activity", "Developer": "Review and improve this codebase"}[role])
    goal = {"Student": "Explain the architecture in beginner-friendly language, define unfamiliar concepts, and create a short learning path with 3 comprehension questions.", "Teacher": "Create a short project review guide, 5 comprehension questions with answers, and a rubric covering architecture, testing, documentation, and maintainability. Avoid claiming unverified facts.", "Developer": "Create a prioritized engineering review with maintainability risks, test ideas, and practical next steps grounded in the supplied project evidence."}[role]
    st.write({"Student": "Understand the main modules, learn prerequisites, and check your understanding.", "Teacher": "Create a classroom discussion guide and questions from the code that is actually available.", "Developer": "Get a focused engineering review and concrete next steps."}[role])
    if st.button(f"Generate {role.lower()} guide with Gemma 4", key="role_guide"):
        with st.spinner("Generating a guide…"):
            try:
                st.session_state["role_guide"] = GemmaService().role_guide(project_name, analysis, role, goal)
            except (ModelConfigurationError, ModelRequestError) as exc:
                st.error(str(exc))
    if st.session_state.get("role_guide"):
        st.markdown(st.session_state["role_guide"])

with tabs[5]:
    st.subheader("Project Readiness Report")
    for check in analysis["readiness"]:
        icon = {"PASS": "✅", "REVIEW": "🟡", "MISSING": "⚪"}.get(check["status"], "ℹ️")
        st.markdown(f"{icon} **{check['title']}** — {check['detail']}")
    st.caption("Readiness checks are intentionally transparent. They do not replace running tests, linting, or a security review.")
    report_md = build_markdown_report(project_name, source_label, analysis, summary)
    st.download_button("Download static report (.md)", report_md, file_name=f"{project_name.lower().replace(' ', '-')}-codemap-report.md", mime="text/markdown")
    if st.button("Add Gemma 4 executive summary", key="exec_summary"):
        with st.spinner("Writing report summary…"):
            try:
                st.session_state["exec_summary"] = GemmaService().executive_summary(project_name, analysis)
            except (ModelConfigurationError, ModelRequestError) as exc:
                st.error(str(exc))
    if st.session_state.get("exec_summary"):
        st.markdown(st.session_state["exec_summary"])

with tabs[6]:
    st.subheader("File Explorer")
    paths = sorted(project_files)
    selected_path = st.selectbox("Select a file", paths)
    if selected_path:
        content = project_files[selected_path]
        st.caption(f"{len(content.splitlines())} lines · {len(content)} characters")
        st.code(content[:20000], language="python" if selected_path.endswith(".py") else "text", line_numbers=True)
        if selected_path.endswith(".py") and st.button("Explain this file with Gemma 4", key="explain_file"):
            with st.spinner("Explaining file…"):
                try:
                    st.session_state["file_explanation"] = GemmaService().explain_file(selected_path, content, role)
                except (ModelConfigurationError, ModelRequestError) as exc:
                    st.error(str(exc))
        if st.session_state.get("file_explanation"):
            st.markdown(st.session_state["file_explanation"])

st.divider()
st.caption("CodeMap MVP · Gemma 4 is used for explanations and recommendations; repository scanning and readiness signals are computed locally. Treat generated advice as suggestions to verify.")
