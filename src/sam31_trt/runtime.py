from __future__ import annotations

from pathlib import Path
from typing import Any

import tensorrt as trt
import torch


TRT_TO_TORCH = {
    trt.float16: torch.float16,
    trt.float32: torch.float32,
    trt.bfloat16: torch.bfloat16,
    trt.int32: torch.int32,
    trt.int64: torch.int64,
    trt.bool: torch.bool,
}


class TensorRTVisionTrunk(torch.nn.Module):
    """Torch-compatible wrapper for the fixed-shape SAM 3.1 vision engine."""

    def __init__(self, engine_path: Path) -> None:
        super().__init__()
        logger = trt.Logger(trt.Logger.WARNING)
        self.runtime = trt.Runtime(logger)
        self.engine = self.runtime.deserialize_cuda_engine(engine_path.read_bytes())
        if self.engine is None:
            raise RuntimeError(f"failed to deserialize TensorRT engine: {engine_path}")
        self.context = self.engine.create_execution_context()
        inputs = []
        outputs = []
        for index in range(self.engine.num_io_tensors):
            name = self.engine.get_tensor_name(index)
            if self.engine.get_tensor_mode(name) == trt.TensorIOMode.INPUT:
                inputs.append(name)
            else:
                outputs.append(name)
        if len(inputs) != 1 or len(outputs) != 1:
            raise RuntimeError(
                f"vision engine must have one input/output, got {inputs}/{outputs}"
            )
        self.input_name = inputs[0]
        self.output_name = outputs[0]
        self.input_dtype = TRT_TO_TORCH[self.engine.get_tensor_dtype(self.input_name)]
        self.output_dtype = TRT_TO_TORCH[self.engine.get_tensor_dtype(self.output_name)]
        self.channel_list = [1024]
        self._output: torch.Tensor | None = None

    def forward(self, tensor_list: Any) -> list[torch.Tensor]:
        image = getattr(tensor_list, "tensors", tensor_list)
        image = image.to(dtype=self.input_dtype).contiguous()
        if not self.context.set_input_shape(self.input_name, tuple(image.shape)):
            raise RuntimeError(f"TensorRT rejected image shape {tuple(image.shape)}")
        output_shape = tuple(self.context.get_tensor_shape(self.output_name))
        if any(dimension < 0 for dimension in output_shape):
            raise RuntimeError(f"unresolved TensorRT output shape: {output_shape}")
        if (
            self._output is None
            or tuple(self._output.shape) != output_shape
            or self._output.device != image.device
        ):
            self._output = torch.empty(
                output_shape, device=image.device, dtype=self.output_dtype
            )
        if not self.context.set_tensor_address(self.input_name, image.data_ptr()):
            raise RuntimeError("failed to bind TensorRT image input")
        if not self.context.set_tensor_address(
            self.output_name, self._output.data_ptr()
        ):
            raise RuntimeError("failed to bind TensorRT embedding output")
        stream = torch.cuda.current_stream(image.device)
        if not self.context.execute_async_v3(stream.cuda_stream):
            raise RuntimeError("TensorRT vision enqueue failed")
        return [self._output]


class LimitedCallsVisionTrunk(torch.nn.Module):
    """Use an accelerated trunk for initial calls, then fall back to native."""

    def __init__(
        self,
        accelerated: torch.nn.Module,
        native: torch.nn.Module,
        call_limit: int,
    ) -> None:
        super().__init__()
        if call_limit <= 0:
            raise ValueError("call_limit must be positive")
        self.accelerated = accelerated
        self.native = native
        self.call_limit = call_limit
        self.calls = 0
        self.channel_list = native.channel_list

    def forward(self, tensor_list: Any):
        self.calls += 1
        if self.calls <= self.call_limit:
            return self.accelerated(tensor_list)
        return self.native(tensor_list)
