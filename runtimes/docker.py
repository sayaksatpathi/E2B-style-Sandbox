import asyncio
import time
import logging
from typing import Optional

import docker
from docker.errors import DockerException, NotFound, APIError

from runtimes.base import SandboxRuntime, SandboxConfig, ExecResult

logger = logging.getLogger(__name__)

TEMPLATE_IMAGES = {
    "python": "python:3.11-slim",
    "node": "node:20-slim",
    "bash": "bash:5.2",
    "go": "golang:1.21-alpine",
    "ruby": "ruby:3.2-slim",
}

NETWORK_NONE = "none"
NETWORK_FULL = "bridge"
RESTRICTED_NETWORK_NAME = "sandbox-restricted"


class DockerRuntime(SandboxRuntime):
    """Docker-based sandbox runtime with resource limits and isolation."""

    def __init__(self):
        self._client: Optional[docker.DockerClient] = None

    def _get_client(self) -> docker.DockerClient:
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    def _ensure_restricted_network(self, client: docker.DockerClient) -> str:
        """Create the sandbox-restricted internal network if it doesn't exist.

        internal=True means Docker adds no NAT rules and the network cannot
        route to external addresses — giving real isolation without 'none'.
        """
        try:
            client.networks.get(RESTRICTED_NETWORK_NAME)
        except docker.errors.NotFound:
            client.networks.create(
                RESTRICTED_NETWORK_NAME,
                driver="bridge",
                internal=True,
                labels={"managed-by": "sandbox-platform"},
            )
        return RESTRICTED_NETWORK_NAME

    async def create(self, config: SandboxConfig) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._create_sync, config)

    def _create_sync(self, config: SandboxConfig) -> str:
        client = self._get_client()
        image = TEMPLATE_IMAGES.get(config.template, "python:3.11-slim")

        try:
            client.images.get(image)
        except docker.errors.ImageNotFound:
            logger.info(f"Pulling image {image}")
            client.images.pull(image)

        nano_cpus = int(config.cpu_limit * 1e9)
        memory_bytes = config.memory_mb * 1024 * 1024

        if config.network_policy == "none":
            network_mode = NETWORK_NONE
            network_name = None
        elif config.network_policy == "restricted":
            network_mode = None
            network_name = self._ensure_restricted_network(client)
        else:  # full
            network_mode = NETWORK_FULL
            network_name = None

        run_kwargs = dict(
            command="sleep infinity",
            detach=True,
            name=f"sandbox-{config.sandbox_id}",
            nano_cpus=nano_cpus,
            mem_limit=memory_bytes,
            memswap_limit=memory_bytes,
            pids_limit=config.pid_limit,
            read_only=False,
            tmpfs={"/tmp": "size=64m,exec"},
            working_dir="/workspace",
            user="nobody",
            remove=False,
            security_opt=["no-new-privileges:true"],
            cap_drop=["ALL"],
            environment={"HOME": "/tmp", "TMPDIR": "/tmp"},
            labels={
                "sandbox.id": config.sandbox_id,
                "sandbox.template": config.template,
                "managed-by": "sandbox-platform",
            },
        )

        if network_mode is not None:
            run_kwargs["network_mode"] = network_mode
        elif network_name is not None:
            run_kwargs["network"] = network_name

        container = client.containers.run(image, **run_kwargs)

        try:
            container.exec_run("mkdir -p /workspace", user="root")
            container.exec_run("chmod 777 /workspace", user="root")
        except Exception as e:
            logger.warning(f"Could not setup workspace: {e}")

        return container.id

    async def destroy(self, container_id: str) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._destroy_sync, container_id)

    def _destroy_sync(self, container_id: str) -> None:
        client = self._get_client()
        try:
            container = client.containers.get(container_id)
            container.stop(timeout=5)
            container.remove(force=True)
        except NotFound:
            logger.warning(f"Container {container_id[:12]} already removed")
        except APIError as e:
            logger.error(f"Error destroying container {container_id[:12]}: {e}")

    async def exec(
        self,
        container_id: str,
        command: str,
        args: list[str],
        timeout_seconds: int,
    ) -> ExecResult:
        loop = asyncio.get_event_loop()
        # asyncio.wait_for provides a safety-net; the real enforcement is the
        # `timeout` binary inside the container which kills the process at the
        # OS level and returns exit code 124.
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    None, self._exec_sync, container_id, command, args, timeout_seconds
                ),
                timeout=timeout_seconds + 15,  # buffer for Docker overhead
            )
        except asyncio.TimeoutError:
            return ExecResult(
                exit_code=124,
                stdout="",
                stderr="Execution timed out (safety net)",
                duration_ms=timeout_seconds * 1000,
                timed_out=True,
            )
        return result

    def _exec_sync(
        self,
        container_id: str,
        command: str,
        args: list[str],
        timeout_seconds: int,
    ) -> ExecResult:
        client = self._get_client()
        container = client.containers.get(container_id)

        # Wrap with the Linux `timeout` utility so the process is killed at the
        # OS level when timeout_seconds elapses.  Exit code 124 = timed out.
        cmd = ["timeout", "--kill-after=2", str(timeout_seconds), command] + args
        start = time.time()

        try:
            exec_result = container.exec_run(
                cmd,
                stdout=True,
                stderr=True,
                demux=True,
                workdir="/workspace",
                user="nobody",
            )
            duration_ms = int((time.time() - start) * 1000)

            stdout_bytes, stderr_bytes = exec_result.output or (b"", b"")
            stdout = (stdout_bytes or b"").decode("utf-8", errors="replace")
            stderr = (stderr_bytes or b"").decode("utf-8", errors="replace")
            exit_code = exec_result.exit_code or 0
            timed_out = exit_code == 124

        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            return ExecResult(
                exit_code=1,
                stdout="",
                stderr=str(e),
                duration_ms=duration_ms,
                timed_out=False,
            )

        return ExecResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
            timed_out=timed_out,
        )

    async def pause(self, container_id: str) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._pause_sync, container_id)

    def _pause_sync(self, container_id: str) -> None:
        client = self._get_client()
        container = client.containers.get(container_id)
        container.pause()

    async def resume(self, container_id: str) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._resume_sync, container_id)

    def _resume_sync(self, container_id: str) -> None:
        client = self._get_client()
        container = client.containers.get(container_id)
        container.unpause()

    async def logs(self, container_id: str, tail: int = 100) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._logs_sync, container_id, tail)

    def _logs_sync(self, container_id: str, tail: int) -> str:
        client = self._get_client()
        try:
            container = client.containers.get(container_id)
            raw = container.logs(tail=tail, stdout=True, stderr=True)
            return raw.decode("utf-8", errors="replace")
        except NotFound:
            return ""

    async def is_running(self, container_id: str) -> bool:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._is_running_sync, container_id)

    def _is_running_sync(self, container_id: str) -> bool:
        client = self._get_client()
        try:
            container = client.containers.get(container_id)
            container.reload()
            return container.status in ("running", "paused")
        except NotFound:
            return False

    async def fork(self, source_container_id: str, new_config: SandboxConfig) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fork_sync, source_container_id, new_config)

    def _fork_sync(self, source_container_id: str, new_config: SandboxConfig) -> str:
        """Commit the source container as an image, then create a new container from it."""
        client = self._get_client()
        source = client.containers.get(source_container_id)
        fork_image = source.commit(
            repository=f"sandbox-fork-{new_config.sandbox_id[:8]}",
            tag="latest",
        )
        TEMPLATE_IMAGES[f"fork-{new_config.sandbox_id[:8]}"] = fork_image.id
        new_config.template = f"fork-{new_config.sandbox_id[:8]}"
        container_id = self._create_sync(new_config)
        del TEMPLATE_IMAGES[f"fork-{new_config.sandbox_id[:8]}"]
        return container_id
