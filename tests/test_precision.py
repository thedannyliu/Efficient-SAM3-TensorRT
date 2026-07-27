import unittest
from pathlib import Path

import onnx

from sam31_trt.precision import PrecisionRule
from scripts.quantize_vision_onnx import evenly_spaced_paths, semantic_scope


class PrecisionRuleTest(unittest.TestCase):
    def test_valid_rule(self) -> None:
        self.assertEqual(PrecisionRule("tracker.*", "fp8").precision, "fp8")

    def test_semantic_scope_keeps_block_hierarchy(self) -> None:
        node = onnx.helper.make_node("MatMul", ["x", "w"], ["y"], name="linear_8")
        node.metadata_props.add(
            key="pkg.torch.onnx.name_scopes",
            value="['', 'blocks.2', 'blocks.2.mlp', 'blocks.2.mlp.fc1', 'linear_8']",
        )

        scope = semantic_scope(node)

        self.assertIn("blocks.2.mlp.fc1", scope)
        self.assertIn("linear_8", scope)

    def test_calibration_paths_span_the_input_pool(self) -> None:
        paths = [Path(f"{index:03}.jpg") for index in range(10)]

        selected = evenly_spaced_paths(paths, 3)

        self.assertEqual(selected, [paths[0], paths[4], paths[9]])

    def test_calibration_limit_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            evenly_spaced_paths([Path("frame.jpg")], 0)

    def test_invalid_precision(self) -> None:
        with self.assertRaises(ValueError):
            PrecisionRule("tracker.*", "int4")


if __name__ == "__main__":
    unittest.main()
