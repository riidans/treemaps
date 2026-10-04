import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from treemap.layout import compute_layout
from treemap.models import FileNode


class LayoutCullingTests(unittest.TestCase):
    def test_invalid_bounds_and_zero_size_root_return_no_items(self):
        root = FileNode(Path("root"), "root", size=10, is_dir=True)
        self.assertEqual(compute_layout(root, (0.0, 0.0, 0.0, 100.0)), [])
        root.size = 0
        self.assertEqual(compute_layout(root, (0.0, 0.0, 100.0, 100.0)), [])

    def test_leaf_root_fills_the_available_bounds(self):
        root = FileNode(Path("file.bin"), "file.bin", size=10)

        items = compute_layout(root, (2.0, 3.0, 40.0, 50.0))

        self.assertEqual(len(items), 1)
        self.assertIs(items[0].node, root)
        self.assertEqual(items[0].rect, (2.0, 3.0, 40.0, 50.0))

    def test_zero_sized_rectangle_from_squarify_is_skipped(self):
        root = FileNode(Path("root"), "root", size=10, is_dir=True)
        root.add_child(FileNode(Path("root/file.bin"), "file.bin", size=10))

        with mock.patch("treemap.layout.squarify", return_value=[(0.0, 0.0, 0.0, 0.0)]):
            self.assertEqual(compute_layout(root, (0.0, 0.0, 100.0, 100.0)), [])

    def test_padding_zero_uses_the_original_child_bounds(self):
        root = FileNode(Path("root"), "root", size=100, is_dir=True)
        child = FileNode(Path("root/child"), "child", size=100, is_dir=True)
        child.add_child(FileNode(Path("root/child/file"), "file", size=100))
        root.add_child(child)

        items = compute_layout(root, (0.0, 0.0, 100.0, 100.0), min_size=0.0, padding=0.0)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].rect, (0.0, 0.0, 100.0, 100.0))

    def test_max_depth_stops_subdivision(self):
        root = FileNode(Path("root"), "root", size=100, is_dir=True)
        child = FileNode(Path("root/child"), "child", size=100, is_dir=True)
        child.add_child(FileNode(Path("root/child/file"), "file", size=100))
        root.add_child(child)

        items = compute_layout(root, (0.0, 0.0, 100.0, 100.0), min_size=0.0, max_depth=1)

        self.assertEqual(len(items), 1)
        self.assertIs(items[0].node, child)

    def test_small_directory_is_expanded_when_size_culling_is_disabled(self):
        root = FileNode(Path("root"), "root", size=100, is_dir=True)
        small_directory = FileNode(Path("root/small"), "small", size=1, is_dir=True)
        small_directory.add_child(
            FileNode(Path("root/small/file.bin"), "file.bin", size=1)
        )
        root.add_child(small_directory)
        root.add_child(FileNode(Path("root/large.bin"), "large.bin", size=99))

        items = compute_layout(root, (0.0, 0.0, 100.0, 100.0), min_size=0.0)

        self.assertEqual(len(items), 2)
        self.assertIn("file.bin", [item.node.name for item in items])
        self.assertNotIn(small_directory, [item.node for item in items])
        self.assertEqual(len(small_directory.children), 1)


if __name__ == "__main__":
    unittest.main()
