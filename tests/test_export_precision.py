import unittest

import torch

from scripts.export_vision_trunk import configure_fp32_layer_norms


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


if __name__ == "__main__":
    unittest.main()
