"""Submit ComfyUI workflows, wait for completion, and fetch their images."""

import json
import time
from typing import Any, cast
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

from imagebench.constants.comfy import DEFAULT_TIMEOUT_S, POLL_INTERVAL_S, REQUEST_TIMEOUT_S
from imagebench.types.benchmark import Job
from imagebench.types.comfy import ImageResult, Workflow
from imagebench.workflow import bind_workflow

__all__ = ["Comfy", "ImageResult"]


class Comfy:
    """Client for a dedicated ComfyUI server with a single job in flight."""

    def __init__(
        self,
        server: str,
        template: Workflow,
        output_node: str,
        timeout: int = DEFAULT_TIMEOUT_S,
        poll: float = POLL_INTERVAL_S,
    ) -> None:
        """Set the workflow and timing limits for one ComfyUI instance."""
        info = urlsplit(server)
        if info.scheme not in {"http", "https"} or not info.hostname:
            raise ValueError("server must be an HTTP(S) base URL")
        if info.username or info.password or info.query or info.fragment:
            raise ValueError("use a base URL without credentials, query or fragment")

        self.server = server.rstrip("/")
        self.template = template
        self.output_node = output_node
        self.timeout = timeout
        self.poll = poll

    def _request(self, path: str, payload: dict[str, Workflow] | None = None) -> bytes:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(self.server + path, data=body, headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=min(REQUEST_TIMEOUT_S, self.timeout)) as response:
                return cast(bytes, response.read())
        except HTTPError as exc:
            detail = exc.read(1000).decode("utf-8", errors="replace")
            raise RuntimeError(f"ComfyUI {path}: HTTP {exc.code}: {detail}") from exc

    def _json(self, path: str, payload: dict[str, Workflow] | None = None) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(self._request(path, payload)))

    def check_idle(self) -> None:
        """Reject submissions that would share the queue with other work."""
        queue = self._json("/queue")
        if queue["queue_running"] or queue["queue_pending"]:
            raise RuntimeError("ComfyUI queue is busy. Use a dedicated server.")

    def _submit(self, graph: Workflow) -> str:
        reply = self._json("/prompt", {"prompt": graph})
        if "prompt_id" not in reply or reply.get("error"):
            raise RuntimeError(f"ComfyUI rejected the workflow: {reply}")
        prompt_id = reply["prompt_id"]
        if not isinstance(prompt_id, str) or not prompt_id.replace("-", "").isalnum():
            raise RuntimeError("unexpected ComfyUI prompt id")
        return prompt_id

    def _wait(self, prompt_id: str, deadline: float) -> dict[str, Any]:
        while time.perf_counter() < deadline:
            history = self._json(f"/history/{prompt_id}")
            entry = history.get(prompt_id)
            if entry:
                status = entry["status"]
                if status["status_str"] != "success" or not status["completed"]:
                    raise RuntimeError(f"ComfyUI job {prompt_id} ended with {status}")
                return cast(dict[str, Any], entry)
            time.sleep(self.poll)
        raise TimeoutError(f"ComfyUI job {prompt_id} did not finish")

    def _image_path(self, entry: dict[str, Any]) -> str:
        images = entry.get("outputs", {}).get(self.output_node, {}).get("images", [])
        if len(images) != 1:
            raise RuntimeError("the selected output node must produce exactly one image")
        image = images[0]
        query = {key: image.get(key, "") for key in ("filename", "type", "subfolder")}
        return "/view?" + urlencode(query)

    def render(self, job: Job) -> ImageResult:
        """Measure generation through history confirmation, then time the download."""
        graph = bind_workflow(self.template, job, f"imagebench/{uuid4().hex}")
        self.check_idle()

        # Include submission and polling in latency, with download timed separately.
        start = time.perf_counter()
        prompt_id = self._submit(graph)
        entry = self._wait(prompt_id, start + self.timeout)
        completed = time.perf_counter()

        path = self._image_path(entry)
        fetch_start = time.perf_counter()
        png = self._request(path)
        return ImageResult(png, completed - start, time.perf_counter() - fetch_start)
