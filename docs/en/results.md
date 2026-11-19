# Resume runs and read results

[OboroLabs](../../README.md) · [Русская версия](../ru/results.md)

## Saved runs

`manifest.json` records the config, runtime description, workflow digest, and server fingerprint. Each PNG in `images/` has a matching JSON in `records/` with its job, timings, and PNG SHA-256.

Rerun the same command to skip verified jobs. A plan mismatch or a corrupted completed record stops the run. Use a new output directory for an independent rerun.

## Timing reports

```bash
oborolabs report out/sample
```

`report/summary.md` gives warm and cold coverage and links to the CSV exports. `records.csv` lists individual jobs. `timing.csv` groups jobs by phase, profile, and image size and shows the median, linearly interpolated p95, and images per minute. With one sample, p95 is blank. Images per minute is 60 divided by mean latency. For a more stable p95, use multiple samples with separate case IDs and seeds.

## External evaluator scores

See [Evaluate image quality](evaluators.md) for the Tesseract and CompBench++ commands and the HPS workflow.

Run your evaluator under its own protocol. Match its outputs to completed warm job IDs from `report/records.csv` and write one finite score per job, metric, evaluator, and evaluator revision.

```csv
job_id,metric,value,evaluator,revision
```

```bash
oborolabs report out/sample --scores evaluator.csv --reference reference
```

`quality.csv` groups scores by evaluator, revision, metric, profile, and size. It reports the mean and how many generated jobs were scored. `pairs.csv` compares each candidate with the specified reference on shared cases at the same size, metric, evaluator, and revision. It reports both score coverages, the number of pairs, the mean score delta (candidate minus reference), and both latency medians on those pairs. A positive delta means the candidate score is higher. Whether higher is better depends on the metric.

Keep the original evaluator outputs for audits and estimate uncertainty separately when the study needs it.
