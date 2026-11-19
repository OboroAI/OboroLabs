# Code layout and tests

[OboroLabs](../../README.md) · [Русская версия](../ru/development.md)

The benchmark client uses the Python 3.11+ standard library. The installed `oborolabs` command and `python3 -m imagebench` run the same CLI.

- [CLI](../../imagebench/cli.py) dispatches commands. [Planning](../../imagebench/plan.py) validates config and enumerates jobs. [Workflow binding](../../imagebench/workflow.py) fills the API graph.
- [Runner](../../imagebench/runner.py) coordinates warm-up and resume. The [ComfyUI client](../../imagebench/comfy.py) measures HTTP requests, and [storage](../../imagebench/storage.py) owns locking, integrity checks, and writes.
- [Reporting](../../imagebench/report.py) exports verified records. [Timing](../../imagebench/timing.py) calculates latency statistics, and [quality](../../imagebench/quality.py) imports scores and compares matched cases.
- [Evaluators](../../imagebench/evaluators) run Tesseract and HPS and exchange inputs and scores with CompBench++.
- [Types](../../imagebench/types) holds shared schemas. [Constants](../../imagebench/constants) holds limits, defaults, and CSV headers.

## Run the tests

```bash
python3 -m unittest discover -s tests -v
```

The tests cover plan and workflow validation, output integrity and locking, timing, evaluator protocols, and end-to-end CLI behavior. They use fixture PNGs, a local mock ComfyUI HTTP server, and fixture evaluator outputs. See ComfyUI's [API route reference](https://docs.comfy.org/development/comfyui-server/comms_routes) for the server endpoints.
