import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import dedupe  # noqa: E402

CONTENT = b"same-content-across-files" * 80  # > one hash chunk? no — small is fine


class DedupeTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "sub").mkdir()
        for name in ("a.bin", "b.bin", Path("sub") / "c.bin"):
            (self.root / name).write_bytes(CONTENT)
        (self.root / "unique.bin").write_bytes(b"totally different" * 5)

    def tearDown(self):
        self._tmp.cleanup()

    def test_finds_one_group_of_three(self):
        groups = dedupe.find_duplicates(self.root, 0)
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]), 3)
        names = {p.name for p in groups[0]}
        self.assertEqual(names, {"a.bin", "b.bin", "c.bin"})

    def test_min_size_filters_small_files(self):
        groups = dedupe.find_duplicates(self.root, 10 * 1024 * 1024)
        self.assertEqual(groups, [])

    def test_move_to_keeps_first_copy(self):
        trash = self.root / "trash"
        dedupe.main([str(self.root), "--move-to", str(trash), "--yes"])
        remaining = {p.name for p in self.root.rglob("*")
                     if p.is_file() and trash not in p.parents}
        self.assertIn("a.bin", remaining)
        self.assertNotIn("b.bin", remaining)
        moved = {p.name for p in trash.iterdir()}
        self.assertEqual(moved, {"b.bin", "c.bin"})

    def test_clean_folder_reports_nothing(self):
        empty = self.root / "empty"
        empty.mkdir()
        self.assertEqual(dedupe.find_duplicates(empty, 0), [])


if __name__ == "__main__":
    unittest.main()
