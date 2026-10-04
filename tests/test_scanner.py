import os
import shutil
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from treemap.models import AggregateLeaf, FileNode
from treemap.scanner import (
    _scan_one_directory,
    aggregate_sizes_post_order,
    scan_directory_dfs,
    scan_filesystem,
)


class _FakeDirEntry:
    def __init__(self, path, name, *, symlink=False, directory=False, size=0):
        self.path = str(path)
        self.name = name
        self._symlink = symlink
        self._directory = directory
        self._size = size

    def is_symlink(self):
        return self._symlink

    def is_dir(self, follow_symlinks=False):
        return self._directory

    def stat(self, follow_symlinks=False):
        return SimpleNamespace(st_size=self._size)


class _FakeScandir:
    def __init__(self, entries):
        self.entries = entries

    def __enter__(self):
        return iter(self.entries)

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class _FailingDirEntry(_FakeDirEntry):
    def __init__(self, path, name, failure):
        super().__init__(path, name)
        self.failure = failure

    def is_symlink(self):
        raise self.failure


class _FailingStatEntry(_FakeDirEntry):
    def stat(self, follow_symlinks=False):
        raise PermissionError("stat denied")


class ScannerTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).parent / "_scanner_fixture"
        self.root.mkdir(exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_deeply_nested_sizes_aggregate_to_root(self):
        root = self.root
        deep = root / "one" / "two" / "three" / "four"
        deep.mkdir(parents=True)
        (deep / "first.bin").write_bytes(b"a" * 7)
        (deep / "second.bin").write_bytes(b"b" * 13)

        tree = scan_filesystem(root)

        self.assertEqual(tree.size, 20)
        node = tree
        for directory_name in ("one", "two", "three", "four"):
            node = next(child for child in node.children if child.name == directory_name)
            self.assertEqual(node.size, 20)

    def test_nested_empty_directories_have_zero_size(self):
        root = self.root
        empty = root / "empty" / "nested" / "directories"
        empty.mkdir(parents=True)

        tree = scan_filesystem(root)

        self.assertEqual(tree.size, 0)
        node = tree
        for directory_name in ("empty", "nested", "directories"):
            node = next(child for child in node.children if child.name == directory_name)
            self.assertTrue(node.is_dir)
            self.assertEqual(node.size, 0)

    @unittest.skipUnless(hasattr(os, "symlink"), "symbolic links are unavailable")
    def test_symlink_loop_is_skipped(self):
        root = self.root
        branch = root / "branch"
        branch.mkdir()
        (branch / "payload.bin").write_bytes(b"payload")
        loop = branch / "loop-to-root"
        try:
            loop.symlink_to(root, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"creating symlinks is unavailable: {exc}")

        tree = scan_filesystem(root)

        self.assertEqual(tree.size, 7)
        branch_node = next(child for child in tree.children if child.name == "branch")
        self.assertEqual(branch_node.size, 7)
        self.assertNotIn("loop-to-root", {child.name for child in branch_node.children})

    def test_cyclic_symlink_entry_is_always_skipped_without_following_it(self):
        root = self.root
        entries = [
            _FakeDirEntry(root / "loop-to-root", "loop-to-root", symlink=True, directory=True),
            _FakeDirEntry(root / "payload.bin", "payload.bin", size=4096),
        ]

        def fake_scandir(path):
            self.assertEqual(Path(path), root.resolve())
            return _FakeScandir(entries)

        with mock.patch("treemap.scanner.os.scandir", side_effect=fake_scandir):
            tree = scan_filesystem(root)

        self.assertEqual(tree.size, 4096)
        self.assertEqual([child.name for child in tree.children], ["payload.bin"])

    def test_permission_denied_directory_is_skipped(self):
        root = self.root
        readable = root / "readable"
        locked = root / "locked"
        readable.mkdir()
        locked.mkdir()
        (readable / "payload.bin").write_bytes(b"12345")

        real_scandir = os.scandir

        def scandir_with_locked_directory_denied(path):
            if Path(path) == locked:
                raise PermissionError("access denied")
            return real_scandir(path)

        with mock.patch("treemap.scanner.os.scandir", side_effect=scandir_with_locked_directory_denied):
            tree = scan_filesystem(root)

        self.assertEqual(tree.size, 5)
        locked_node = next(child for child in tree.children if child.name == "locked")
        self.assertEqual(locked_node.size, 0)
        self.assertEqual(locked_node.children, [])

    def test_small_files_roll_up_without_individual_file_nodes(self):
        root = self.root
        (root / "tiny-a.txt").write_bytes(b"a" * 3)
        (root / "tiny-b.txt").write_bytes(b"b" * 4095)
        (root / "boundary.bin").write_bytes(b"c" * 4096)

        tree = scan_filesystem(root)

        aggregate = next(child for child in tree.children if isinstance(child, AggregateLeaf))
        self.assertEqual(aggregate.count, 2)
        self.assertEqual(aggregate.size, 4098)
        self.assertEqual(aggregate.name, "Other files (2)")
        self.assertIn("boundary.bin", {child.name for child in tree.children})
        self.assertEqual(tree.size, 8194)

    def test_file_stat_error_is_counted_as_zero_size(self):
        entry = _FailingStatEntry(self.root / "unreadable.bin", "unreadable.bin")

        with mock.patch("treemap.scanner.os.scandir", return_value=_FakeScandir([entry])):
            result = _scan_one_directory(self.root)

        self.assertEqual(result.file_count, 1)
        self.assertEqual(result.small_file_count, 1)
        self.assertEqual(result.small_file_size, 0)

    def test_entry_permission_error_is_skipped(self):
        entry = _FailingDirEntry(self.root / "denied", "denied", PermissionError("denied"))

        with mock.patch("treemap.scanner.os.scandir", return_value=_FakeScandir([entry])):
            result = _scan_one_directory(self.root)

        self.assertEqual(result.file_count, 0)
        self.assertEqual(result.directories, [])

    def test_directory_scandir_error_returns_an_empty_result(self):
        with mock.patch("treemap.scanner.os.scandir", side_effect=PermissionError("denied")):
            result = _scan_one_directory(self.root)

        self.assertEqual(result.files, [])
        self.assertEqual(result.directories, [])

    def test_progress_callback_reports_discovered_files(self):
        (self.root / "payload.bin").write_bytes(b"x" * 4096)
        progress = []

        scan_directory_dfs(self.root, on_progress=lambda path, count: progress.append((path, count)))

        self.assertTrue(progress)
        self.assertEqual(progress[-1][1], 1)

    def test_scanning_a_regular_file_returns_a_file_node(self):
        file_path = self.root / "single.bin"
        file_path.write_bytes(b"payload")

        node = scan_filesystem(file_path)

        self.assertFalse(node.is_dir)
        self.assertEqual(node.size, 7)

    def test_missing_scan_target_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            scan_filesystem(self.root / "does-not-exist")

    def test_aggregate_sizes_handles_a_file_root(self):
        node = FileNode(Path("file.bin"), "file.bin", size=12)

        self.assertEqual(aggregate_sizes_post_order(node), 12)


if __name__ == "__main__":
    unittest.main()
