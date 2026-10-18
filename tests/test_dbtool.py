import argparse
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import dbtool  # noqa: E402


def make_db(path: Path, with_age: bool = False, extra_table: bool = False, rows: int = 2):
    con = sqlite3.connect(str(path))
    cols = "id INTEGER PRIMARY KEY, name TEXT" + (", age INTEGER" if with_age else "")
    con.execute(f"CREATE TABLE users ({cols})")
    con.executemany("INSERT INTO users (name) VALUES (?)", [(f"user{i}",) for i in range(rows)])
    if extra_table:
        con.execute("CREATE TABLE logs (id INTEGER PRIMARY KEY, msg TEXT)")
    con.commit()
    con.close()


class DbtoolTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.old = self.root / "old.db"
        self.new = self.root / "new.db"
        make_db(self.old)
        make_db(self.new, with_age=True, extra_table=True, rows=3)

    def tearDown(self):
        self._tmp.cleanup()

    def test_diff_reports_schema_changes(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            dbtool.main(["diff", str(self.old), str(self.new)])
        out = buffer.getvalue()
        self.assertIn("table added", out)
        self.assertIn("logs", out)
        self.assertIn("users.age", out)
        self.assertIn("rows", out)

    def test_diff_identical_databases(self):
        same = self.root / "same.db"
        make_db(same)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            dbtool.main(["diff", str(self.old), str(same)])
        self.assertIn("identical", buffer.getvalue())

    def test_dump_json(self):
        out = self.root / "dump.json"
        dbtool.main(["dump", str(self.old), "--format", "json", "-o", str(out)])
        data = json.loads(out.read_text(encoding="utf-8"))
        self.assertIn("users", data)
        self.assertEqual(len(data["users"]), 2)

    def test_query_prints_rows(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            dbtool.main(["query", str(self.old), "SELECT * FROM users ORDER BY id"])
        self.assertIn("user0", buffer.getvalue())
        self.assertIn("user1", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
