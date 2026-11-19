"""Command-line arguments and dispatch for the benchmark."""

import argparse
from pathlib import Path

from imagebench.constants.benchmark import COLD, WARM
from imagebench.constants.comfy import DEFAULT_TIMEOUT_S
from imagebench.evaluators.compbench import export_compbench, import_compbench
from imagebench.evaluators.hps import evaluate_hps
from imagebench.evaluators.ocr import evaluate_ocr
from imagebench.plan import load, make_jobs
from imagebench.report import report
from imagebench.runner import run

__all__ = ["main"]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OboroLabs model benchmarks with ComfyUI.")
    commands = parser.add_subparsers(dest="command", required=True)

    plan_parser = commands.add_parser("plan", help="Validate a config and list warm job IDs.")
    plan_parser.add_argument("config", type=Path)

    run_parser = commands.add_parser("run", help="Submit new jobs and resume verified records.")
    run_parser.add_argument("config", type=Path)
    run_parser.add_argument("output", type=Path)
    run_parser.add_argument("--server", required=True, help="ComfyUI HTTP(S) base URL.")
    run_parser.add_argument("--phase", choices=(WARM, COLD), default=WARM)
    run_parser.add_argument("--profile", help="Select one configured profile.")
    run_parser.add_argument("--case", help="Select one configured case.")
    run_parser.add_argument("--fresh-server", action="store_true")
    run_parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S)

    report_parser = commands.add_parser("report", help="Export timing and optional evaluator summaries.")
    report_parser.add_argument("output", type=Path)
    report_parser.add_argument("--scores", type=Path)
    report_parser.add_argument("--reference", help="Reference profile for paired deltas.")

    ocr_parser = commands.add_parser("ocr", help="Score single-line text rendering with Tesseract.")
    ocr_parser.add_argument("run_dir", type=Path)
    ocr_parser.add_argument("references", type=Path, help="CSV with case_id, language and text.")
    ocr_parser.add_argument("output", type=Path, help="Destination scores CSV.")

    hps_parser = commands.add_parser("hps", help="Score warm images using the optional HPS v2.0 evaluator.")
    hps_parser.add_argument("run_dir", type=Path)
    hps_parser.add_argument("checkpoint", type=Path, help="Pinned HPS_v2_compressed.pt checkpoint.")
    hps_parser.add_argument("output", type=Path, help="Destination scores CSV.")

    compbench_export = commands.add_parser(
        "compbench-export", help="Prepare inputs for the CompBench++ CLIP evaluator."
    )
    compbench_export.add_argument("run_dir", type=Path)
    compbench_export.add_argument("prompts", type=Path, help="CompBench++ non-spatial prompt list.")
    compbench_export.add_argument("bundle", type=Path, help="New output directory for evaluator inputs.")

    compbench_import = commands.add_parser("compbench-import", help="Convert CompBench++ CLIP results to a scores CSV.")
    compbench_import.add_argument("bundle", type=Path)
    compbench_import.add_argument("output", type=Path, help="Destination scores CSV.")
    return parser


def _run_benchmark(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if args.timeout < 1:
        parser.error("--timeout must be positive")
    if args.phase == COLD and not (args.profile and args.case and args.fresh_server):
        parser.error("cold needs --profile, --case, and --fresh-server")

    plan, workflow = load(args.config)
    run(
        plan,
        workflow,
        args.output,
        args.server,
        args.phase,
        args.profile,
        args.case,
        args.timeout,
    )


def main() -> None:
    """Run the requested subcommand with consistent CLI error handling."""
    parser = _build_parser()
    args = parser.parse_args()
    try:
        if args.command == "plan":
            plan, _ = load(args.config)
            for job in make_jobs(plan):
                print(job["id"])
        elif args.command == "run":
            _run_benchmark(args, parser)
        elif args.command == "report":
            if args.reference and not args.scores:
                parser.error("--reference requires --scores")
            report(args.output, args.scores, args.reference)
        elif args.command == "ocr":
            evaluate_ocr(args.run_dir, args.references, args.output)
        elif args.command == "hps":
            evaluate_hps(args.run_dir, args.checkpoint, args.output)
        elif args.command == "compbench-export":
            export_compbench(args.run_dir, args.prompts, args.bundle)
        else:
            import_compbench(args.bundle, args.output)
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        parser.exit(1, f"imagebench: {exc}\n")
