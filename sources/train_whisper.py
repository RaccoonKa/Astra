import sys
import torch

_orig_torch_load = torch.load
def _safe_load(*args, **kwargs):
    kwargs["weights_only"] = False
    return _orig_torch_load(*args, **kwargs)
torch.load = _safe_load

from piper_train.__main__ import main

if __name__ == "__main__":
    torch.set_float32_matmul_precision("high")

    args = [
        "--dataset-dir", "training_dir",
        "--accelerator", "gpu",
        "--devices", "1",
        "--batch-size", "8",
        "--validation-split", "0.0",
        "--num-test-examples", "0",
        "--max_epochs", "6000",
        "--resume_from_checkpoint", "irina.ckpt",
        "--checkpoint-epochs", "10",
        "--precision", "32",
        "--log_every_n_steps", "5"
    ]
    sys.argv[1:] = args
    main()