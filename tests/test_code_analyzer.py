import unittest
from code_analyzer import analyze_project, build_graphviz
from github_loader import _is_allowed, load_zip_project
import io
import zipfile


class AnalyzerTests(unittest.TestCase):
    def test_detects_import_edge(self):
        files = {
            "app.py": "from helper import greet\ndef main():\n    return greet()\n",
            "helper.py": "def greet():\n    return 'hi'\n",
            "README.md": "# Demo\n",
            "requirements.txt": "",
            "test_app.py": "def test_smoke():\n    assert True\n",
        }
        result = analyze_project(files)
        self.assertIn(("app.py", "helper.py"), result["graph_edges"])
        self.assertEqual(result["totals"]["functions"], 3)
        self.assertIn("digraph CodeMap", build_graphviz(result))

    def test_detects_missing_tests(self):
        result = analyze_project({"app.py": "def main():\n    return 1\n"})
        self.assertTrue(any("tests" in x["title"].lower() for x in result["findings"]))

    def test_path_filter(self):
        self.assertFalse(_is_allowed("../../.env"))
        self.assertFalse(_is_allowed("src/.env"))
        self.assertTrue(_is_allowed("src/app.py"))

    def test_zip_loading_without_extracting(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr("demo/app.py", "def hello():\n    return 'hello'\n")
            archive.writestr("demo/.env", "SECRET=do-not-read")
        name, files = load_zip_project(data.getvalue(), "demo.zip")
        self.assertEqual(name, "demo")
        self.assertIn("demo/app.py", files)
        self.assertFalse(any(path.endswith(".env") for path in files))


if __name__ == "__main__":
    unittest.main()
