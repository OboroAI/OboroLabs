# Evaluate image quality

[OboroLabs](../../README.md) · [Русская версия](../ru/evaluators.md)

Evaluators read completed warm images. Each score is linked to its job ID so the report can compare quality and latency on the same cases. Tesseract and HPS run from the OboroLabs CLI. CompBench++ runs its upstream scoring script in a separate environment.

## Tesseract OCR

Install Tesseract and the language data used by your cases. For the bilingual example, install `eng` and `rus`. See the [Tesseract installation guide](https://tesseract-ocr.github.io/tessdoc/Installation.html).

**macOS with Homebrew**

```bash
brew install tesseract tesseract-lang
```

**Ubuntu or Debian**

```bash
sudo apt install tesseract-ocr tesseract-ocr-eng tesseract-ocr-rus
```

Once the [SD 1.5 checkpoint and ComfyUI](running.md#install-comfyui) are ready, generate the example posters and score them. Set `COMFY_URL` to your running instance.

```bash
tesseract --list-langs
oborolabs run examples/ocr.config.json out/ocr --server "$COMFY_URL"
oborolabs ocr out/ocr examples/ocr-references.csv out/ocr/ocr-scores.csv
oborolabs report out/ocr --scores out/ocr/ocr-scores.csv
```

The [reference CSV](../../examples/ocr-references.csv) specifies the expected text and OCR language for each case ID. All profiles share the same reference for each case. The adapter uses the single-line protocol from the Oboro Blink study. It passes `--oem 1 --psm 7`, then applies NFKC normalization, case folding, and whitespace collapse. The `ocr_exact` metric is 1 for an exact match and 0 otherwise. The `ocr_cer` metric divides Levenshtein edit distance by the length of the normalized reference. Lower CER is better, and extra text can push it above 1. The `.raw.json` sidecar retains the original recognition, reference text, language, and engine version. For historical replication, pin Tesseract 5.3.4 and record the language data checksums. [Tesseract CLI reference](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html)

## T2I-CompBench++ non-spatial

This protocol measures image-to-prompt similarity on the non-spatial split with the upstream ViT-B/32 CLIP scorer. The original Oboro Blink pilot used three validation prompts with ten seeds each. OboroLabs exports the images and maps the original scores back to jobs. [Pinned upstream scorer](https://github.com/Karine-Huang/T2I-CompBench/blob/4aa404212eb5d06e5adbcd9cee696c750d0d25a5/CLIPScore_eval/CLIP_similarity.py)

From the OboroLabs project directory, clone the scorer and use a separate Python environment for its dependencies. Install `torch` and `torchvision` in that environment according to the [PyTorch installation selector](https://pytorch.org/get-started/locally/).

```bash
git clone https://github.com/Karine-Huang/T2I-CompBench.git
git -C T2I-CompBench checkout --detach 4aa404212eb5d06e5adbcd9cee696c750d0d25a5
python3.11 -m venv .venv-compbench
# Install the matching torch and torchvision builds with .venv-compbench/bin/python -m pip.
.venv-compbench/bin/python -m pip install -r requirements-compbench.txt
.venv-compbench/bin/python -m spacy download en_core_web_sm
```

Create cases with exact prompt lines from `T2I-CompBench/examples/dataset/non_spatial_val.txt`. Use a separate case ID for each seed. Keep the prompt, seed, and dimensions fixed across profiles. Once these cases have run in `out/compbench-run`, export and score them.

```bash
oborolabs compbench-export out/compbench-run \
  T2I-CompBench/examples/dataset/non_spatial_val.txt out/compbench-eval
.venv-compbench/bin/python T2I-CompBench/CLIPScore_eval/CLIP_similarity.py \
  --outpath out/compbench-eval
oborolabs compbench-import out/compbench-eval out/compbench-run/compbench-scores.csv
oborolabs report out/compbench-run --scores out/compbench-run/compbench-scores.csv --reference reference
```

The bundle keeps `jobs.csv` and the upstream `annotation_clip/vqa_result.json` for audit. Set `--reference` to the baseline profile in your config. Pick the official evaluator for each additional CompBench++ category and import its original per-image scores using the [CSV contract](results.md#external-evaluator-scores).

## HPS v2.0

The Oboro Blink study also used HPS v2.0 on HPDv2 prompts. Download the [pinned HPS v2.0 checkpoint](https://huggingface.co/xswu/HPSv2/blob/697403c78157020a1ae59d23f111aa58ced35b0a/HPS_v2_compressed.pt) and save it as `out/HPS_v2_compressed.pt`. Install the scorer in its own Python environment. Use the [PyTorch selector](https://pytorch.org/get-started/locally/) if your hardware needs a specific build.

```bash
python3.11 -m venv .venv-hps
.venv-hps/bin/python -m pip install -r requirements.txt -r requirements-hps.txt
.venv-hps/bin/oborolabs hps out/sample out/HPS_v2_compressed.pt out/sample/hps-scores.csv
.venv-hps/bin/oborolabs report out/sample --scores out/sample/hps-scores.csv --reference reference
```

The adapter checks the checkpoint SHA-256, sends each verified warm PNG to the [upstream HPS scorer](https://github.com/tgxs002/HPSv2/tree/866735ecaae999fa714bd9edfa05aa2672669ee3) with its exact prompt, and exports `hps_v2_0_x100` using the study's published scale. The score revision records the evaluator package version and checkpoint revision.

For the original sampling protocol, use six prompts per style from the pinned [HPDv2 benchmark dataset](https://huggingface.co/datasets/zhwang/HPDv2/tree/b9517430f34b1080d4f741118d2a440155a165cd), with the same seed and size across profiles for each case. Keep the original scores when calculating uncertainty.
