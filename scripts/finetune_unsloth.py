"""
Fine-tune Qwen2.5-Coder with Unsloth (LoRA / QLoRA).

Requires:
  - NVIDIA GPU + CUDA
  - Unsloth installed (from d:\\LLM\\unsloth or pip)
  - Dataset at data/coding_qa.jsonl

On this machine (Intel UHD only), training will not run.
Use Google Colab with a free T4, or any NVIDIA GPU PC, then export GGUF
and load it in Ollama for offline chat.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "coding_qa.jsonl"
DEFAULT_OUT = ROOT / "outputs" / "qwen25-coder-lora"
MODEL_NAME = "unsloth/Qwen2.5-Coder-1.5B-Instruct"


def require_cuda() -> None:
    try:
        import torch
    except ImportError as exc:
        raise SystemExit(
            "PyTorch not installed. Install Unsloth Core first "
            "(see coding-bot/README.md)."
        ) from exc
    if not torch.cuda.is_available():
        raise SystemExit(
            "No NVIDIA CUDA GPU detected.\n"
            "Unsloth QLoRA fine-tuning needs an NVIDIA GPU.\n"
            "This PC has Intel UHD only — use Colab/T4 or another GPU machine.\n"
            "Offline chat already works via Ollama:  py -3 scripts\\chat.py"
        )


def load_rows(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if not rows:
        raise SystemExit(f"Dataset empty: {path}")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--model", default=MODEL_NAME)
    parser.add_argument("--max-steps", type=int, default=60)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = load_rows(args.data)
    print(f"Dataset: {args.data} ({len(rows)} examples)")
    print(f"Model:   {args.model}")
    print(f"Output:  {args.out}")

    if args.dry_run:
        print("Dry-run OK — dataset readable.")
        return 0

    require_cuda()

    from unsloth import FastLanguageModel
    from datasets import Dataset
    from trl import SFTTrainer, SFTConfig

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.model,
        max_seq_length=2048,
        load_in_4bit=True,
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        lora_alpha=16,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=3407,
    )

    dataset = Dataset.from_list(rows)

    def formatting(examples):
        texts = []
        for messages in examples["messages"]:
            texts.append(
                tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=False
                )
            )
        return {"text": texts}

    dataset = dataset.map(formatting, batched=True, remove_columns=dataset.column_names)

    args.out.mkdir(parents=True, exist_ok=True)
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        args=SFTConfig(
            output_dir=str(args.out),
            per_device_train_batch_size=1,
            gradient_accumulation_steps=8,
            warmup_steps=5,
            max_steps=args.max_steps,
            learning_rate=2e-4,
            logging_steps=1,
            optim="adamw_8bit",
            weight_decay=0.01,
            lr_scheduler_type="linear",
            seed=3407,
            report_to="none",
            dataset_text_field="text",
            max_seq_length=2048,
        ),
    )
    trainer.train()
    model.save_pretrained(str(args.out))
    tokenizer.save_pretrained(str(args.out))
    print(f"Saved LoRA adapter to {args.out}")
    print("Next: merge/export to GGUF, then `ollama create` for offline use.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
