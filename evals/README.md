# Extraction model eval harness

Answers one question with data instead of assumption: **which local
model should power meeting extraction?** (plan §8, §2).

```bash
uv run python evals/run_eval.py --model gpt-oss:20b --model qwen3:14b
```

Requires a running `ollama serve` with the models under test pulled. Add
`--json-out path.json` to save raw per-case results.

## Methodology

`golden/*.json` holds hand-written Turkish meeting excerpts with
expected outcomes: keyword groups an extracted action title must match,
count bounds on actions/decisions, an expected owner substring, and (for
one case) a flag that the model must *not* fabricate a due date from a
vague timeframe. `metrics.py` scores each run with plain substring/range
checks — deliberately not another LLM call, since a judge that's itself
unreliable can't be trusted to answer the question the harness exists
for.

Six cases, intentionally small and adversarial rather than broad:
correct action + owner + weekday, a real decision, a transcript with
*no* action items (must return empty, not invent one), an ambiguous
timeframe (must not hallucinate a date), a multi-topic excerpt, and an
owner-precision case where two people are named but only one commits.

## Latest run (2026-09-16, RTX 5060 Ti 16GB)

First pass, before tightening the prompts — **includes the finding, not
just the fix**:

| model | pass | recall | Turkish % | avg latency |
|---|---|---|---|---|
| gpt-oss:20b | 3/6 | 0.67 | 50% | 7.8s |
| qwen3:14b | 3/6 | 0.83 | 100% | 20.0s |

`gpt-oss:20b` produced fluent, correct extractions — but titled them in
**English** on 3 of 6 cases despite an all-Turkish transcript and a
Turkish-language system prompt that never explicitly said "write the
output in Turkish." That gap — not a deeper model limitation — was the
actual cause.

Fix: added one explicit rule to `services/prompts/v1/action_items.md`
and `decisions.md` ("title/summary alanını HER ZAMAN Türkçe yaz... ASLA
İngilizceye çevirme") plus a rule against counting a personal commitment
("ben hazırlarım") as a decision, which had been inflating both models'
false-positive decision count. Re-run after the fix:

| model | pass | recall | Turkish % | avg latency |
|---|---|---|---|---|
| gpt-oss:20b | 6/6 | 1.00 | 100% | 8.0s |
| qwen3:14b | 6/6 | 1.00 | 100% | 20.7s |

A follow-up manual check of free-form Turkish prose (the `prose_model`
role — meeting summaries, not JSON-schema output) found both models
produce fluent, idiomatic Turkish summaries of the same transcript, with
no meaningful quality gap.

**Conclusion:** with an explicit Turkish-output instruction in the
prompt, `gpt-oss:20b` matches `qwen3:14b` on both structured-extraction
correctness and Turkish fluency, while running ~2.5x faster and fitting
one model instead of two on a 16GB card. `config.py` now defaults
`prose_model` to `gpt-oss:20b` too — see its docstring. This is a
starting point measured on six small, English-authored cases, not a
permanent verdict: re-run this harness after any prompt change, after
adding real user-corrected cases from `training_examples`, or if you're
choosing between models on different hardware.

## Extending the golden set

The highest-value next cases: real (anonymized) transcript excerpts
pulled from your own `training_examples` table — see plan §7's
fine-tuning data pipeline, which reads from the same table.
