import unittest

from sam31_trt.upstream_compat import (
    supported_kwargs,
    validate_vision_state_mismatch,
)


class UpstreamCompatibilityTest(unittest.TestCase):
    def test_supported_kwargs_removes_unknown_arguments(self) -> None:
        def init_state(resource_path: str, async_loading_frames: bool = False) -> None:
            pass

        filtered = supported_kwargs(
            init_state,
            {
                "resource_path": "frames",
                "async_loading_frames": False,
                "offload_state_to_cpu": False,
            },
        )
        self.assertEqual(
            filtered,
            {"resource_path": "frames", "async_loading_frames": False},
        )

    def test_derived_rope_buffers_are_allowed(self) -> None:
        missing = [
            "blocks.0.attn.freqs_cis_real",
            "blocks.31.attn.freqs_cis_imag",
        ]
        self.assertEqual(validate_vision_state_mismatch(missing, []), missing)

    def test_learned_weight_mismatch_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            validate_vision_state_mismatch(["blocks.0.attn.qkv.weight"], [])


if __name__ == "__main__":
    unittest.main()
