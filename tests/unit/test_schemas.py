import pytest
from pydantic import ValidationError
from api.schemas import CreateSandboxRequest, ExecRequest


def test_create_sandbox_defaults():
    req = CreateSandboxRequest()
    assert req.template == "python"
    assert req.ttl_seconds == 300
    assert req.cpu_limit == 1.0
    assert req.memory_mb == 512


def test_create_sandbox_invalid_template():
    with pytest.raises(ValidationError):
        CreateSandboxRequest(template="windows")


def test_create_sandbox_ttl_bounds():
    with pytest.raises(ValidationError):
        CreateSandboxRequest(ttl_seconds=10)
    with pytest.raises(ValidationError):
        CreateSandboxRequest(ttl_seconds=9999)


def test_exec_request_command_injection():
    with pytest.raises(ValidationError):
        ExecRequest(command="python; rm -rf /")

    with pytest.raises(ValidationError):
        ExecRequest(command="ls && cat /etc/passwd")


def test_exec_request_valid():
    req = ExecRequest(command="python", args=["-c", "print(1)"], timeout=10)
    assert req.command == "python"
    assert req.args == ["-c", "print(1)"]
