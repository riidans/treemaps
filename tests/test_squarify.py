import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from treemap.squarify import squarify, worst


class WorstAspectRatioTests(unittest.TestCase):
    def test_empty_or_invalid_inputs_are_infinite(self):
        self.assertEqual(worst([], 10), math.inf)
        self.assertEqual(worst([1, 2], 0), math.inf)
        self.assertEqual(worst([0, 0], 10), math.inf)
        self.assertEqual(worst([1, 0], 10), math.inf)

    def test_uses_smallest_area_for_the_thin_side(self):
        # The second term is driven by min(R), not max(R).
        self.assertAlmostEqual(worst([4, 1], 2), 6.25)


class SquarifyTests(unittest.TestCase):
    def test_empty_or_non_positive_bounds_return_zero_rectangles(self):
        self.assertEqual(squarify([], (3, 4, 10, 10)), [])
        self.assertEqual(squarify([1, 2], (3, 4, 0, 10)), [(3, 4, 0.0, 0.0)] * 2)
        self.assertEqual(squarify([1, 2], (3, 4, 10, -1)), [(3, 4, 0.0, 0.0)] * 2)

    def test_non_positive_sizes_are_omitted_but_original_indices_are_preserved(self):
        rectangles = squarify([2, 0, -1, 2], (0, 0, 10, 10))

        self.assertEqual(rectangles[1], (0, 0, 0.0, 0.0))
        self.assertEqual(rectangles[2], (0, 0, 0.0, 0.0))
        self.assertAlmostEqual(rectangles[0][2] * rectangles[0][3], 50)
        self.assertAlmostEqual(rectangles[3][2] * rectangles[3][3], 50)

    def test_all_non_positive_sizes_return_zero_rectangles(self):
        self.assertEqual(
            squarify([0, -1], (3, 4, 10, 10)),
            [(3, 4, 0.0, 0.0), (3, 4, 0.0, 0.0)],
        )

    def test_equal_sizes_fill_a_square_without_gaps(self):
        rectangles = squarify([1, 1], (10, 20, 10, 10))

        self.assertEqual(rectangles, [(10, 20, 5.0, 10.0), (15.0, 20, 5.0, 10.0)])

    def test_each_positive_rectangle_has_proportional_area(self):
        sizes = [6, 3, 1]
        bounds = (2, 5, 20, 10)
        rectangles = squarify(sizes, bounds)

        self.assertEqual(len(rectangles), len(sizes))
        for size, (_, _, width, height) in zip(sizes, rectangles):
            self.assertAlmostEqual(width * height, 200 * size / sum(sizes))
        self.assertTrue(all(width >= 0 and height >= 0 for _, _, width, height in rectangles))


if __name__ == "__main__":
    unittest.main()
