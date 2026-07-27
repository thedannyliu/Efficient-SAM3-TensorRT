import unittest

import torch

from sam31_trt.runtime import LimitedCallsVisionTrunk


class FakeTrunk(torch.nn.Module):
    channel_list = [4]

    def __init__(self, value: int) -> None:
        super().__init__()
        self.value = value

    def forward(self, _input):
        return [self.value]


class RuntimeDispatchTest(unittest.TestCase):
    def test_accelerated_call_limit_then_native(self) -> None:
        trunk = LimitedCallsVisionTrunk(FakeTrunk(1), FakeTrunk(2), call_limit=1)

        self.assertEqual(trunk(None), [1])
        self.assertEqual(trunk(None), [2])
        self.assertEqual(trunk.calls, 2)

    def test_call_limit_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            LimitedCallsVisionTrunk(FakeTrunk(1), FakeTrunk(2), call_limit=0)


if __name__ == "__main__":
    unittest.main()
