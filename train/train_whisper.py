import sys
import torch
import os

_orig_torch_load = torch.load

def _safe_load(*args, **kwargs):
    kwargs["weights_only"] = False
    return _orig_torch_load(*args, **kwargs)

torch.load = _safe_load

from piper_train.__main__ import main

if __name__ == "__main__":
    torch.set_float32_matmul_precision("high")

    log_dir = "training_dir_whisper/logs"
    os.makedirs(log_dir, exist_ok=True)

    args = [
        "--dataset-dir", "training_dir_whisper",
        "--accelerator", "gpu",
        "--devices", "1",
        "--batch-size", "16",
        "--validation-split", "0.0",
        "--num-test-examples", "0",
        "--max_epochs", "4000",
        "--resume_from_checkpoint", "irina.ckpt",
        "--checkpoint-epochs", "50",
        "--precision", "16-mixed",
        "--log_every_n_steps", "10",
        "--default-root-dir", log_dir
    ]

    sys.argv[1:] = args
    print("Starting Whisper voice fine-tuning...")
    main()