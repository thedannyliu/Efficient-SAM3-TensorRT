import unittest

import onnx

from scripts.set_onnx_output_dtype import set_output_dtype


class OnnxOutputDtypeTest(unittest.TestCase):
    def test_adds_bf16_output_cast(self) -> None:
        graph = onnx.helper.make_graph(
            [onnx.helper.make_node("Identity", ["input"], ["output"])],
            "test",
            [onnx.helper.make_tensor_value_info("input", onnx.TensorProto.FLOAT, [1])],
            [
                onnx.helper.make_tensor_value_info(
                    "output", onnx.TensorProto.FLOAT, [1]
                )
            ],
        )
        model = onnx.helper.make_model(graph)

        set_output_dtype(model, onnx.TensorProto.BFLOAT16)

        self.assertEqual(model.graph.output[0].name, "output_cast")
        self.assertEqual(
            model.graph.output[0].type.tensor_type.elem_type,
            onnx.TensorProto.BFLOAT16,
        )
        self.assertEqual(model.graph.node[-1].op_type, "Cast")
        self.assertEqual(model.graph.node[-1].input[0], "output")


if __name__ == "__main__":
    unittest.main()
