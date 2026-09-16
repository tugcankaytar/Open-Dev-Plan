#!/usr/bin/env python3
"""LoRA fine-tune gpt-oss-20b on your own approved/corrected extractions
(plan §7), via Unsloth + QLoRA.

    uv sync --extra train         # installs unsloth, transformers, peft, trl
    uv run python training/export_dataset.py --out training/dataset.jsonl
    uv run python training/train_lora.py --data training/dataset.jsonl

Not run automatically by anything in this repo — this is a reference
implementation you run yourself once export_dataset.py's dataset has
enough examples (see MIN_RECOMMENDED_EXAMPLES there; below that
threshold, iterating on services/prompts/v1/*.md usually helps more).

Needs ~14GB VRAM for 4-bit QLoRA on the 20B model (Unsloth's own
figure); expect a 16GB card to be fully occupied during training — stop
`ollama serve` and the app's own worker first.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True, help="JSONL from export_dataset.py")
    parser.add_argument("--val-data", type=Path, default=None)
    parser.add_argument("--base-model", default="unsloth/gpt-oss-20b-unsloth-bnb-4bit")
    parser.add_argument("--output-dir", type=Path, default=Path("training/output/lora-adapter"))
    parser.add_argument("--max-seq-length", type=int, default=4096)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--batch-size", type=int, default=2)
    args = parser.parse_args()

    try:
        from datasets import load_dataset
        from trl import SFTConfig, SFTTrainer
        from unsloth import FastLanguageModel
    except ImportError as exc:
        raise SystemExit(
            f"Missing training dependencies. Run: uv sync --extra train\n(original error: {exc})"
        ) from exc

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.base_model,
        max_seq_length=args.max_seq_length,
        load_in_4bit=True,
    )
    target_modules = [
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
        "gate_proj",
        "up_proj",
        "down_proj",
    ]
    model = FastLanguageModel.get_peft_model(
        model,
        r=args.lora_r,
        target_modules=target_modules,
        lora_alpha=args.lora_r * 2,
        lora_dropout=0.0,
        bias="none",
        use_gradient_checkpointing="unsloth",
    )

    dataset = load_dataset("json", data_files=str(args.data), split="train")
    eval_dataset = None
    if args.val_data:
        eval_dataset = load_dataset("json", data_files=str(args.val_data), split="train")

    def format_example(example: dict) -> dict:
        text = tokenizer.apply_chat_template(
            example["messages"], tokenize=False, add_generation_prompt=False
        )
        return {"text": text}

    dataset = dataset.map(format_example)
    if eval_dataset is not None:
        eval_dataset = eval_dataset.map(format_example)

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        eval_dataset=eval_dataset,
        args=SFTConfig(
            output_dir=str(args.output_dir),
            per_device_train_batch_size=args.batch_size,
            gradient_accumulation_steps=4,
            num_train_epochs=args.epochs,
            learning_rate=args.learning_rate,
            logging_steps=10,
            save_strategy="epoch",
            eval_strategy="epoch" if eval_dataset is not None else "no",
            dataset_text_field="text",
            max_seq_length=args.max_seq_length,
            bf16=True,
        ),
    )

    trainer.train()
    model.save_pretrained(str(args.output_dir))
    tokenizer.save_pretrained(str(args.output_dir))

    (args.output_dir / "training_args.json").write_text(
        json.dumps(vars(args), indent=2, default=str), encoding="utf-8"
    )
    print(f"\nSaved LoRA adapter to {args.output_dir}")
    print("Next: merge + convert to GGUF, then `ollama create` — see training/README.md.")
    print(
        "IMPORTANT: before switching the app to the new model, re-run "
        "evals/run_eval.py against it and confirm it doesn't regress "
        "versus the base model (plan §7's acceptance gate)."
    )


if __name__ == "__main__":
    main()
