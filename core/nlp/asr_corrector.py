from pathlib import Path
import torch
import onnxruntime as ort


session_options = ort.SessionOptions()
session_options.intra_op_num_threads = 2
session_options.inter_op_num_threads = 1
session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL

if not hasattr(torch, "int4"):
    torch.int4 = torch.int8
if not hasattr(torch, "uint4"):
    torch.uint4 = torch.uint8

from transformers import AutoTokenizer
from optimum.onnxruntime import ORTModelForSeq2SeqLM

class ASRCorrector:
    def __init__(self, model_dir: str = None):
        if model_dir is None:
            base_dir = Path(__file__).resolve().parent.parent.parent
            model_dir = str(base_dir / "optimized_models" / "corrector")

        self.tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
        self.model = ORTModelForSeq2SeqLM.from_pretrained(
            model_dir,
            local_files_only=True,
            use_io_binding=False
        )

    def correct(self, text: str) -> str:
        clean_text = text.strip().lower() if text else ""
        if not clean_text:
            return ""

        inputs = self.tokenizer(clean_text, return_tensors="pt")
        outputs = self.model.generate(
            **inputs,
            max_new_tokens=40,
            num_beams=2,
            early_stopping=True,
            do_sample=False
        )
        corrected = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        return corrected.strip()