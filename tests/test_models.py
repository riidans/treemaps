import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from treemap.models import FileNode


class FileNodeTests(unittest.TestCase):
    def test_add_child_sets_parent_and_remove_child_clears_it(self):
        parent = FileNode(Path("root"), "root", is_dir=True)
        child = FileNode(Path("root/file.txt"), "file.txt", size=12)

        parent.add_child(child)
        self.assertIs(child.parent, parent)
        self.assertIn(child, parent.children)

        parent.remove_child(child)
        self.assertNotIn(child, parent.children)
        self.assertIsNone(child.parent)

    def test_each_node_has_independent_children_list(self):
        first = FileNode(Path("first"), "first", is_dir=True)
        second = FileNode(Path("second"), "second", is_dir=True)

        first.add_child(FileNode(Path("first/file"), "file"))

        self.assertEqual(len(first.children), 1)
        self.assertEqual(second.children, [])


if __name__ == "__main__":
    unittest.main()
