import io
import os
import re
import zipfile
from pathlib import Path

import frontmatter
import streamlit as st
import streamlit.components.v1 as components

# Set page config (must be first Streamlit command)
st.set_page_config(
    page_title="Problem Solving Coach",
    page_icon="🎯",
    layout="wide",
)

# Coach data directory
COACH_DATA_DIR = Path(__file__).parent / ".coach-data"
COMPLETED_FILE = COACH_DATA_DIR / "completed.txt"
CURRENT_PROBLEM_FILE = COACH_DATA_DIR / "current_problem.txt"
HISTORY_FILE = COACH_DATA_DIR / "history.txt"
HISTORY_LIMIT = 10


class CoachData:
    """Manages persistent coach data: completed problems, current problem, history."""

    def __init__(self):
        COACH_DATA_DIR.mkdir(exist_ok=True)
        COMPLETED_FILE.touch(exist_ok=True)
        HISTORY_FILE.touch(exist_ok=True)
        CURRENT_PROBLEM_FILE.touch(exist_ok=True)
        st.session_state.current_problem_id = None

    @property
    def completed(self) -> set[str]:
        """Set of completed problem directory names."""
        return set(COMPLETED_FILE.read_text().strip().splitlines())

    def add_completed(self, problem_id: str) -> None:
        completed = self.completed
        completed.add(problem_id)
        COMPLETED_FILE.write_text("\n".join(sorted(completed)))

    def remove_completed(self, problem_id: str) -> None:
        completed = self.completed
        completed.discard(problem_id)
        COMPLETED_FILE.write_text("\n".join(sorted(completed)))

    @property
    def current_problem(self) -> str | None:
        """Current problem directory name."""
        content = CURRENT_PROBLEM_FILE.read_text().strip()
        st.session_state.current_problem_id = content
        return st.session_state.current_problem_id

    def set_current_problem(self, problem_id: str) -> None:
        CURRENT_PROBLEM_FILE.write_text(problem_id)
        st.session_state.current_problem_id = problem_id

    @property
    def history(self) -> list[str]:
        """List of problem directory names (most recent first)."""
        content = HISTORY_FILE.read_text().strip()
        return content.splitlines() if content else []

    def add_to_history(self, problem_id: str) -> None:
        """Add problem to history, keeping only the most recent HISTORY_LIMIT items."""
        history = list(self.history)

        if problem_id in history:
            history.remove(problem_id)
        history.insert(0, problem_id)

        history = history[:HISTORY_LIMIT]

        HISTORY_FILE.write_text("\n".join(history))


def render_mermaid(mermaid_code: str, height: int = 400):
    """Render Mermaid diagram using HTML component"""
    components.html(
        f"""
        <script type="module">
            import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
            mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
        </script>
        <div class="mermaid">
{mermaid_code}
        </div>
        """,
        height=height,
        scrolling=False,
    )


def render_markdown_with_mermaid(content: str):
    """Render markdown with Mermaid diagrams extracted and rendered separately"""

    # Find all mermaid blocks with their positions
    mermaid_pattern = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)
    mermaid_matches = list(mermaid_pattern.finditer(content))

    if not mermaid_matches:
        # No mermaid, render as-is
        st.markdown(content)
        return

    # Split content by mermaid blocks and render
    last_end = 0
    diagram_num = 1

    for match in mermaid_matches:
        # Render content before this mermaid block
        before_content = content[last_end : match.start()]
        if before_content.strip():
            st.markdown(before_content)

        # Render the mermaid diagram
        mermaid_code = match.group(1).strip()
        st.markdown(f"### Diagram {diagram_num}")
        render_mermaid(mermaid_code)
        st.markdown("---")
        diagram_num += 1

        last_end = match.end()

    # Render remaining content after last mermaid block
    if last_end < len(content):
        remaining = content[last_end:]
        if remaining.strip():
            st.markdown(remaining)


def render_metadata(metadata: dict[str, object]):
    rendered_metadata = []
    for k, v in metadata.items():
        if k == "name":
            continue
        rendered_metadata.append(f"{k.title()}: <b>{v}</b>")

    st.html("<br>".join(rendered_metadata))


@st.dialog("Solution", width="medium")
def open_in_dialog(file_path: Path):
    st.markdown(file_path.read_text())


class ProblemDetail:
    def __init__(
        self,
        directory: Path,
        metadata: dict[str, object],
        content: str,
        coach_data: CoachData,
    ):
        self.directory = directory
        self.metadata = metadata
        self.content = content
        self.coach_data = coach_data
        self.group = self.directory.parent.name

        self.step_files = list(sorted(directory.glob("step*.md")))
        self.solution_file = directory.joinpath("solution.md")

        self.lab_path = None
        if directory.joinpath("lab").exists():
            self.lab_path = directory.joinpath("lab")

    @property
    def id(self) -> str:
        """Relative path from learning-materials/ as unique identifier."""
        learning_materials = Path(__file__).parent / "learning-materials"
        return str(self.directory.relative_to(learning_materials))

    @property
    def is_completed(self) -> bool:
        return self.id in self.coach_data.completed

    def mark_as_completed(self):
        self.coach_data.add_completed(self.id)

    def unmark_as_completed(self):
        self.coach_data.remove_completed(self.id)

    def __str__(self) -> str:
        completion_sign = " ✅" if self.is_completed else ""
        return f"{str(self.metadata['name'])}{completion_sign}"

    def lab_file(self) -> io.BytesIO:
        if self.lab_path is None:
            raise ValueError("lab_path should be valid")

        zip_buffer = io.BytesIO()

        # Create the zip file within the buffer
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for root, _, files in os.walk(self.lab_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    zip_file.write(
                        file_path, arcname=os.path.relpath(file_path, self.lab_path)
                    )

        zip_buffer.seek(0)

        return zip_buffer


def main():
    """Main app - problem file selector"""

    coach_data = CoachData()

    problem_md_files = Path(__file__).parent.glob("learning-materials/**/problem.md")

    problems: list[ProblemDetail] = []

    for md_file in problem_md_files:
        with open(md_file) as f:
            parsed_markdown = frontmatter.load(f)

            problem = ProblemDetail(
                directory=Path(md_file).parent,
                content=parsed_markdown.content,
                metadata=parsed_markdown.metadata,
                coach_data=coach_data,
            )
            problems.append(problem)

    # Build lookup by problem_id for finding saved/current problems
    problems_by_id: dict[str, ProblemDetail] = {p.id: p for p in problems}

    grouped_problems: dict[str, list[ProblemDetail]] = {}

    for problem in problems:
        group_name = str(problem.group)

        if group_name not in grouped_problems:
            grouped_problems[group_name] = []

        grouped_problems[group_name].append(problem)

    # Sidebar
    with st.sidebar:
        st.header("🎯 Problem Solving Coach")

        category_index = 0
        problem_index = 0

        problem_id = coach_data.current_problem
        if problem_id in problems_by_id:
            history_problem = problems_by_id[problem_id]
            history_category = str(history_problem.group)
            category_index = list(grouped_problems.keys()).index(history_category)
            problem_index = grouped_problems[history_category].index(history_problem)

        category = st.selectbox(
            "Category", list(grouped_problems.keys()), index=category_index
        )
        selected = st.selectbox(
            "Problem", grouped_problems[category], index=problem_index
        )

        coach_data.set_current_problem(selected.id)

        coach_data.add_to_history(selected.id)

        history = coach_data.history
        history_problems = [
            problems_by_id[p_id] for p_id in history if p_id in problems_by_id
        ]

        if history_problems:
            st.markdown("---")
            st.markdown("### 📜 Recent")
            for history_problem in history_problems:
                if st.button(
                    str(history_problem.metadata["name"]),
                    key=f"history_item_{history_problem.id}",
                    type="tertiary",
                ):
                    coach_data.set_current_problem(history_problem.id)
                    st.rerun()

        st.markdown("---")
        st.markdown("### Instructions")
        st.markdown("1. Read the problem")
        st.markdown("2. Think about the questions")
        st.markdown("3. Check `step-01.md` for hints")

    render_metadata(selected.metadata)

    if selected.lab_path is not None:
        st.download_button(
            "Download lab files",
            file_name=f"{selected}-lab.zip",
            data=selected.lab_file(),
            mime="application/zip",
        )

    # Completion toggle button
    if selected.is_completed:
        st.button(
            "✅ Completed - Click to unmark",
            on_click=lambda: selected.unmark_as_completed(),
        )
    else:
        st.button(
            "⬜ Mark as Completed",
            on_click=lambda: selected.mark_as_completed(),
        )

    render_markdown_with_mermaid(selected.content)

    for hint in selected.step_files:
        if st.button(hint.name, key=f"hint_{hint}"):
            open_in_dialog(hint)

    with st.expander("I give up"):
        if st.button("The Solution"):
            open_in_dialog(selected.solution_file)


if __name__ == "__main__":
    main()
