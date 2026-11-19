# Оценка качества изображений

[OboroLabs](../../README.ru.md) · [English](../en/evaluators.md)

Оценщики используют изображения из завершённых заданий с прогревом. Каждая оценка привязана к ID задания, чтобы отчёт сравнивал качество и скорость на одних и тех же случаях. Tesseract и HPS запускаются через CLI OboroLabs. CompBench++ использует исходный скрипт оценки в отдельном окружении.

## Tesseract OCR

Установите Tesseract и языковые данные для своих промптов. Для двуязычного примера нужны `eng` и `rus`. [Руководство по установке Tesseract](https://tesseract-ocr.github.io/tessdoc/Installation.html)

**macOS с Homebrew**

```bash
brew install tesseract tesseract-lang
```

**Ubuntu или Debian**

```bash
sudo apt install tesseract-ocr tesseract-ocr-eng tesseract-ocr-rus
```

После настройки [ComfyUI и чекпойнта SD 1.5](running.md#установить-comfyui) сгенерируйте тестовые постеры и оцените их. Укажите адрес запущенного ComfyUI в `COMFY_URL`.

```bash
tesseract --list-langs
oborolabs run examples/ocr.config.json out/ocr --server "$COMFY_URL"
oborolabs ocr out/ocr examples/ocr-references.csv out/ocr/ocr-scores.csv
oborolabs report out/ocr --scores out/ocr/ocr-scores.csv
```

В [CSV с эталонами](../../examples/ocr-references.csv) для каждого ID случая заданы ожидаемый текст и язык OCR. Один эталон используется для всех профилей. Для однострочных постеров адаптер применяет настройки исследования Oboro Blink `--oem 1 --psm 7`. Затем он нормализует строки по NFKC, приводит регистр через casefold и сворачивает пробелы. Метрика `ocr_exact` равна 1 при точном совпадении и 0 при расхождении. Метрика `ocr_cer` делит расстояние Левенштейна на длину нормализованного эталона. Чем меньше ошибка, тем лучше. Лишний текст может поднять CER выше 1. Файл `.raw.json` сохраняет исходное распознавание, эталон, язык и версию движка. Для воспроизведения исходного эксперимента используйте Tesseract 5.3.4 и зафиксируйте хеши языковых данных. [Справочник CLI Tesseract](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html)

## T2I-CompBench++ non-spatial

Этот протокол измеряет сходство изображения с промптом на подвыборке непространственных отношений (non-spatial) с CLIP ViT-B/32. В исходном пилоте Oboro Blink использовали три промпта валидационной выборки и десять seed на промпт. OboroLabs экспортирует изображения и сопоставляет оценки исходного скрипта с заданиями. [Зафиксированная версия оценщика](https://github.com/Karine-Huang/T2I-CompBench/blob/4aa404212eb5d06e5adbcd9cee696c750d0d25a5/CLIPScore_eval/CLIP_similarity.py)

Из папки OboroLabs скачайте исходники оценщика и создайте отдельное окружение. Установите в нём `torch` и `torchvision` по [инструкции PyTorch для своего оборудования](https://pytorch.org/get-started/locally/).

```bash
git clone https://github.com/Karine-Huang/T2I-CompBench.git
git -C T2I-CompBench checkout --detach 4aa404212eb5d06e5adbcd9cee696c750d0d25a5
python3.11 -m venv .venv-compbench
# Установите подходящие сборки torch и torchvision через .venv-compbench/bin/python -m pip.
.venv-compbench/bin/python -m pip install -r requirements-compbench.txt
.venv-compbench/bin/python -m spacy download en_core_web_sm
```

Для поля `prompt` в случаях используйте точные строки из `T2I-CompBench/examples/dataset/non_spatial_val.txt`. Для каждого seed задайте отдельный ID. В разных профилях одному случаю должны соответствовать одинаковые промпт, seed и размеры. После завершения генерации в `out/compbench-run` экспортируйте изображения и запустите оценщик.

```bash
oborolabs compbench-export out/compbench-run \
  T2I-CompBench/examples/dataset/non_spatial_val.txt out/compbench-eval
.venv-compbench/bin/python T2I-CompBench/CLIPScore_eval/CLIP_similarity.py \
  --outpath out/compbench-eval
oborolabs compbench-import out/compbench-eval out/compbench-run/compbench-scores.csv
oborolabs report out/compbench-run --scores out/compbench-run/compbench-scores.csv --reference reference
```

В папке экспорта остаются таблица соответствия `jobs.csv` и исходный вывод `annotation_clip/vqa_result.json`. Подставьте ID эталонного профиля в `--reference`. Для других категорий CompBench++ используйте их официальные оценщики и импортируйте исходные оценки по изображениям в [формате CSV](results.md#оценки-внешних-инструментов).

## HPS v2.0

В исследовании Oboro Blink также использовали HPS v2.0 на промптах HPDv2. Скачайте [чекпойнт HPS v2.0 из нужной ревизии](https://huggingface.co/xswu/HPSv2/blob/697403c78157020a1ae59d23f111aa58ced35b0a/HPS_v2_compressed.pt) и сохраните его как `out/HPS_v2_compressed.pt`. Установите оценщик в отдельное окружение Python. Если нужна сборка под конкретное оборудование, выберите её по [инструкции PyTorch](https://pytorch.org/get-started/locally/).

```bash
python3.11 -m venv .venv-hps
.venv-hps/bin/python -m pip install -r requirements.txt -r requirements-hps.txt
.venv-hps/bin/oborolabs hps out/sample out/HPS_v2_compressed.pt out/sample/hps-scores.csv
.venv-hps/bin/oborolabs report out/sample --scores out/sample/hps-scores.csv --reference reference
```

Адаптер проверяет SHA-256 чекпойнта, отправляет каждый проверенный PNG и его точный промпт в [исходный оценщик HPS](https://github.com/tgxs002/HPSv2/tree/866735ecaae999fa714bd9edfa05aa2672669ee3) и экспортирует `hps_v2_0_x100` в шкале исходного исследования. В поле ревизии записываются версия пакета оценщика и ревизия чекпойнта.

Для исходной схемы выборки возьмите по шесть промптов на стиль из зафиксированной ревизии [HPDv2](https://huggingface.co/datasets/zhwang/HPDv2/tree/b9517430f34b1080d4f741118d2a440155a165cd). Для каждого случая сохраняйте тот же seed и размер во всех профилях. Храните исходные оценки для расчёта неопределённости.
