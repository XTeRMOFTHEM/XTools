import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import filemux  # noqa: E402


class FilemuxTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        for name in ("photo.jpg", "doc.pdf", "song.mp3", "archive.zip", "weird.xyz"):
            (self.root / name).write_bytes(b"x" * 32)

    def tearDown(self):
        self._tmp.cleanup()

    def test_dry_run_moves_nothing(self):
        filemux.main([str(self.root)])
        for name in ("photo.jpg", "doc.pdf", "song.mp3", "archive.zip", "weird.xyz"):
            self.assertTrue((self.root / name).exists(), f"{name} was moved during dry run")

    def test_apply_organizes_by_type(self):
        filemux.main([str(self.root), "--apply"])
        self.assertTrue((self.root / "Images" / "photo.jpg").exists())
        self.assertTrue((self.root / "Documents" / "doc.pdf").exists())
        self.assertTrue((self.root / "Audio" / "song.mp3").exists())
        self.assertTrue((self.root / "Archives" / "archive.zip").exists())
        self.assertTrue((self.root / "Other" / "weird.xyz").exists())

    def test_undo_restores_everything(self):
        filemux.main([str(self.root), "--apply"])
        filemux.main([str(self.root), "--undo"])
        for name in ("photo.jpg", "doc.pdf", "song.mp3", "archive.zip", "weird.xyz"):
            self.assertTrue((self.root / name).exists(), f"{name} was not restored")
        self.assertFalse((self.root / "Images").exists(), "empty category folders should be cleaned up")

    def test_name_collision_gets_suffix(self):
        (self.root / "Images").mkdir()
        (self.root / "Images" / "photo.jpg").write_bytes(b"pre-existing")
        filemux.main([str(self.root), "--apply"])
        self.assertTrue((self.root / "Images" / "photo.jpg").exists())
        self.assertTrue((self.root / "Images" / "photo (1).jpg").exists())

    def test_organize_by_ext(self):
        filemux.main([str(self.root), "--by", "ext", "--apply"])
        self.assertTrue((self.root / "jpg" / "photo.jpg").exists())
        self.assertTrue((self.root / "xyz" / "weird.xyz").exists())


if __name__ == "__main__":
    unittest.main()
