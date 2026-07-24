import unittest

from sam31_trt.results import compare_candidate


class ResultsTest(unittest.TestCase):
    def test_candidate_acceptance_and_speedup(self) -> None:
        reference = {
            "backend": "pytorch",
            "gpu": "H200",
            "mean_iou": 0.8,
            "mean_latency_ms": 40.0,
        }
        candidate = {
            "backend": "tensorrt",
            "gpu": "H200",
            "mean_iou": 0.72,
            "mean_latency_ms": 20.0,
        }
        report = compare_candidate(reference, candidate)
        self.assertTrue(report["accepted"])
        self.assertAlmostEqual(report["miou_retention"], 0.9)
        self.assertAlmostEqual(report["speedup"], 2.0)


if __name__ == "__main__":
    unittest.main()

