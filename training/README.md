# Fine-tuning runbook (plan §7)

Turns your own approved/edited/rejected proposals into a fine-tuned
extraction model. Nothing here runs automatically — you decide when
you've used the app enough to have a worthwhile dataset, and you decide
whether the result is actually better (the eval-gate step below is not
optional).

## 0. Prerequisites

```bash
uv sync --extra train   # unsloth, transformers, peft, trl — not installed by default
```

QLoRA fine-tuning of gpt-oss-20b needs ~14GB VRAM ([Unsloth's own
figure](https://unsloth.ai/blog/gpt-oss)) — on a 16GB card, stop
`ollama serve` and the app itself first; training will use the whole
GPU.

## 1. Check you have enough data

```bash
uv run python training/export_dataset.py --out training/dataset.jsonl
```

Reads the `training_examples` table (populated automatically every time
a proposal is approved, edited, or rejected — see
`src/odp/services/proposals/resolve.py`) and writes:

- `training/dataset.jsonl` — SFT training split
- `training/dataset.val.jsonl` — SFT validation split (10% by default)
- `training/dataset.rejected.jsonl` — rejected completions (see §4)

Below ~300-500 examples, per plan §7, spend the time on
`services/prompts/v1/*.md` instead — the script prints a reminder if
you're under that line.

## 2. Train the LoRA adapter

```bash
uv run python training/train_lora.py --data training/dataset.jsonl --val-data training/dataset.val.jsonl
```

`train_lora.py` is a reference implementation (Unsloth `FastLanguageModel`
+ `trl.SFTTrainer`) you're expected to read and adjust — dataset size,
GPU, and how much you care about training time all push the
hyperparameters (`--lora-r`, `--epochs`, `--learning-rate`) around.
Output lands in `training/output/lora-adapter/`.

## 3. Merge and convert to GGUF, then load into Ollama

Unsloth can export merged 16-bit weights directly:

```python
model.save_pretrained_merged("training/output/merged", tokenizer, save_method="merged_16bit")
```

then convert with `llama.cpp`'s `convert-hf-to-gguf.py` (see
[Unsloth's GGUF guide](https://unsloth.ai/docs/models/gpt-oss-how-to-run-and-fine-tune)
for exact steps, which change as tooling evolves faster than this file
would stay accurate). Fill `training/Modelfile.template`'s
`__GGUF_PATH__`/`__NUM_CTX__` placeholders and:

```bash
ollama create odp-tr:v1 -f training/Modelfile.template
```

## 4. Gate on the eval harness — do not skip this

```bash
uv run python evals/run_eval.py --model odp-tr:v1 --model gpt-oss:20b
```

If `odp-tr:v1` doesn't beat the base model on `evals/golden/`, it isn't
better — a fine-tune is not automatically an improvement (plan §7).
Extend `evals/golden/` with real (anonymized) cases from your own
`training_examples` before trusting the comparison; six small
English-authored cases (the current set) is a starting point, not a
final answer.

## 5. Use it

```bash
export ODP_EXTRACTION_MODEL=odp-tr:v1   # or set in .env
uv run odp serve
```

Switching back to `gpt-oss:20b` is just re-setting the env var — nothing
about the schema, proposals flow, or database changes.

## On DPO pairs

`training/dataset.rejected.jsonl` holds rejected completions with no
paired "chosen" completion — a user saying no doesn't by itself produce
the right answer. Building real DPO pairs needs either a later
correction on a similar case (matched by hand or by embedding similarity
against `sqlite-vec`, once slice 6's hybrid search lands) or a
human-written chosen completion. Left as a manual step for now; SFT on
the approved/edited data alone is the higher-value, lower-effort path.
