import unittest

from sam31_trt.precision import PrecisionRule


class PrecisionRuleTest(unittest.TestCase):
    def test_valid_rule(self) -> None:
        self.assertEqual(PrecisionRule("tracker.*", "fp8").precision, "fp8")

    def test_invalid_precision(self) -> None:
        with self.assertRaises(ValueError):
            PrecisionRule("tracker.*", "int4")


if __name__ == "__main__":
    unittest.main()

