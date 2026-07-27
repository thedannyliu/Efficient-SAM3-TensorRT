import unittest

import torch

from scripts.export_vision_trunk import (
    FP32Block,
    configure_fp32_layer_norms,
    fp32_softmax_sdpa,
    parse_fp32_blocks,
)


class ExportPrecisionTest(unittest.TestCase):
    def test_layer_norm_uses_fp32_and_preserves_output_dtype(self) -> None:
        model = torch.nn.Sequential(torch.nn.LayerNorm(4)).half()
        value = torch.tensor([[1000.0, 1000.5, 999.5, 1001.0]], dtype=torch.float16)

        count = configure_fp32_layer_norms(model)
        output = model(value)
        expected = torch.nn.functional.layer_norm(
            value.float(),
            (4,),
            model[0].weight.float(),
            model[0].bias.float(),
            model[0].eps,
        ).half()

        self.assertEqual(count, 1)
        self.assertEqual(output.dtype, torch.float16)
        torch.testing.assert_close(output, expected)

    def test_attention_uses_fp32_softmax_and_preserves_dtype(self) -> None:
        torch.manual_seed(7)
        query = torch.randn(1, 2, 8, 4, dtype=torch.float16)
        key = torch.randn(1, 2, 8, 4, dtype=torch.float16)
        value = torch.randn(1, 2, 8, 4, dtype=torch.float16)

        output = fp32_softmax_sdpa(query, key, value)
        expected = torch.nn.functional.scaled_dot_product_attention(
            query.float(), key.float(), value.float()
        ).half()

        self.assertEqual(output.dtype, torch.float16)
        torch.testing.assert_close(output, expected, atol=2e-3, rtol=2e-3)

    def test_fp32_block_preserves_external_dtype(self) -> None:
        wrapped = FP32Block(torch.nn.Linear(4, 4).half())
        output = wrapped(torch.ones(2, 4, dtype=torch.float16))

        self.assertEqual(output.dtype, torch.float16)
        self.assertEqual(wrapped.block.weight.dtype, torch.float32)

    def test_fp32_block_list(self) -> None:
        self.assertEqual(parse_fp32_blocks("7,0,7"), [0, 7])
        with self.assertRaises(ValueError):
            parse_fp32_blocks("32")


if __name__ == "__main__":
    unittest.main()
