import torch
import onnxruntime as ort
from transformers import AutoTokenizer
from optimum.onnxruntime import ORTModelForSeq2SeqLM
from core.utils.config import get_resource_path


class ASRCorrector:
    def __init__(self, model_dir: str = None):
        if model_dir is None:
            model_dir = get_resource_path("optimized_models", "corrector")

        self.tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)

        session_options = ort.SessionOptions()
        session_options.intra_op_num_threads = 4
        session_options.inter_op_num_threads = 2
        session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        self.model = ORTModelForSeq2SeqLM.from_pretrained(
            model_dir,
            local_files_only=True,
            provider="CPUExecutionProvider",
            use_io_binding=False,
            session_options=session_options,
            encoder_file_name="encoder_model.onnx",
            decoder_file_name="decoder_model.onnx",
            decoder_with_past_file_name="decoder_with_past_model.onnx"
        )

    def correct(self, text: str) -> str:
        clean_text = text.strip().lower() if text else ""
        if not clean_text:
            return ""

        word_count = len(clean_text.split())
        max_tokens = min(20, max(5, word_count * 2))

        try:
            inputs = self.tokenizer(clean_text, return_tensors="pt")
            with torch.inference_mode():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    num_beams=1,
                    do_sample=False
                )
            corrected = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            return corrected.strip()
        except Exception as e:
            print(f"[ASR Corrector Warning]: {e}")
            return clean_text