# Configure and run a benchmark

[OboroLabs](../../README.md) · [Русская версия](../ru/running.md)

## Install ComfyUI

OboroLabs is the benchmark client. ComfyUI runs generation in a separate process and can be on the same machine or on a dedicated server.

1. For Apple Silicon, open the [Comfy Desktop for macOS guide](https://docs.comfy.org/installation/desktop/macos) and get the installer from [Comfy's download page](https://comfy.org/download). For a Linux server or a source installation, use the [official manual installation guide](https://docs.comfy.org/installation/manual_install) and select the PyTorch build for your hardware.
2. For the included smoke config, download [the SD 1.5 checkpoint](https://huggingface.co/Comfy-Org/stable-diffusion-1.5/blob/main/v1-5-pruned-emaonly-fp16.safetensors) into the installation's checkpoints folder. A manual installation uses `ComfyUI/models/checkpoints/`. Select it in the Load Checkpoint node if you want to try the model in the UI first. [ComfyUI text-to-image guide](https://docs.comfy.org/tutorials/basic/text-to-image)
3. Start the local ComfyUI instance and copy its base URL. A manual instance started with default settings uses `http://127.0.0.1:8188`. Desktop and remote instances can show a different address or port. [ComfyUI server defaults](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy/cli_args.py)

## Run a smoke benchmark

Install OboroLabs from the [project directory](../../README.md#quick-start). In the same terminal, set `COMFY_URL` to the address from the preceding step.

```bash
export COMFY_URL=http://127.0.0.1:8188
oborolabs plan examples/smoke.config.json
oborolabs run examples/smoke.config.json out/smoke --server "$COMFY_URL"
oborolabs report out/smoke
```

The smoke config needs one checkpoint and writes one measured image plus `out/smoke/report/summary.md`.

## Configuration

1. Copy [config.json](../../examples/config.json) and [workflow.api.json](../../examples/workflow.api.json) into a working directory. In the config, set checkpoint filenames visible to the server and describe its runtime in `runtime`. Record the model `revision` and lowercase `sha256` on each profile when available.
2. Use the example workflow for compatible checkpoints or export your own API-format ComfyUI graph. Use `$prompt`, `$seed`, `$width`, `$height`, `$checkpoint`, `$steps`, and `$filename` as whole JSON string values. The client inserts seed, dimensions, and steps as numbers. The configured `output_node` must return one PNG, and the graph and its custom nodes must support the configured parameters.
3. Use a dedicated idle ComfyUI server with default node caching. Keep each case's prompt, seed, and dimensions fixed across profiles. The sampler must consume the bound seed. Set `COMFY_URL` to the server's base URL.

## Warm runs

```bash
oborolabs plan examples/config.json
oborolabs run examples/config.json out/sample --server "$COMFY_URL"
```

Before each pending profile and size, the client runs the graph once with a seed outside the case set. The client checks the queue before every submission and aborts if it is busy. Use a fresh dedicated server for each study to control caching and other workloads.

Latency is wall-clock time from the HTTP submission through completion confirmed by polling. It includes any queue wait and server-side image writes. The client times the download separately and writes the local PNG after the download measurement.

## Process-cold samples

Start a fresh ComfyUI process and wait for its API to become ready. Before sending any other work to the process, select a single profile and case and mark the run with `--fresh-server`. Repeat the restart before each cold sample.

```bash
oborolabs run examples/config.json out/sample --server "$COMFY_URL" \
  --phase cold --profile candidate --case cube --fresh-server
```

The measurement starts at submission and includes lazy checkpoint loading. The server starts outside the measurement window, and the operating system's page cache can remain warm.

[Resume a run or generate a report](results.md)
