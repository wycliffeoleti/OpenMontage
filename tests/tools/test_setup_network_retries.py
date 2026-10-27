"""Outages retry; permissions, auth and broken inference fail visibly."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import os
import signal

import httpx
import pytest


def _setup():
    path = Path(__file__).resolve().parents[2] / "scripts/setup_local_models.py"
    spec = importlib.util.spec_from_file_location("network_setup", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_network_outage_retries_until_connection_returns(monkeypatch):
    setup = _setup()
    calls = []
    pauses = []
    def transfer():
        calls.append(1)
        if len(calls) < 4:
            raise httpx.ConnectError("temporary DNS failure")
        return "download complete"
    monkeypatch.setattr(setup.time, "sleep", pauses.append)
    assert setup.retry_network(transfer) == "download complete"
    assert pauses == [60, 60, 60]


@pytest.mark.parametrize("status,retries", [(401, False), (403, False), (429, True), (503, True)])
def test_http_statuses_distinguish_retryable_from_permanent_errors(monkeypatch, status, retries):
    setup = _setup()
    calls = []
    error = httpx.HTTPStatusError("HTTP failure", request=httpx.Request("GET", "https://example.com"),
                                  response=httpx.Response(status))
    def transfer():
        calls.append(1)
        if len(calls) == 1:
            raise error
        return "done"
    monkeypatch.setattr(setup.time, "sleep", lambda seconds: None)
    if retries:
        assert setup.retry_network(transfer) == "done"
    else:
        with pytest.raises(httpx.HTTPStatusError):
            setup.retry_network(transfer)
        assert len(calls) == 1


@pytest.mark.parametrize("error", [PermissionError("read-only target"), OSError(28, "No space left on device"), RuntimeError("CUDA out of memory"), KeyboardInterrupt()])
def test_non_network_failures_and_user_interrupt_are_not_retried(monkeypatch, error):
    setup = _setup()
    monkeypatch.setattr(setup.time, "sleep", lambda seconds: pytest.fail("must not retry"))
    def fail():
        raise error
    with pytest.raises(type(error)):
        setup.retry_network(fail)


def test_installer_retries_network_exit_and_preserves_existing_cache(monkeypatch, tmp_path):
    setup = _setup()
    cached = tmp_path / "completed-cache-file"
    cached.write_bytes(b"already downloaded")
    counter = tmp_path / "attempts"
    code = """from pathlib import Path
import sys
counter = Path(sys.argv[1])
attempt = int(counter.read_text()) + 1 if counter.exists() else 1
counter.write_text(str(attempt))
if attempt < 3:
    print('httpx.ConnectError: temporary failure in name resolution')
    sys.exit(1)
print('INSTALL COMPLETE')
"""
    monkeypatch.setattr(setup.time, "sleep", lambda seconds: None)
    log = tmp_path / "install.log"
    setup.retry_network(lambda: setup.run_download_command([sys.executable, "-c", code, str(counter)], log))
    assert counter.read_text() == "3"
    assert cached.read_bytes() == b"already downloaded"
    assert "INSTALL COMPLETE" in log.read_text()


def test_prior_network_error_in_log_does_not_hide_new_permanent_error(tmp_path):
    setup = _setup()
    log = tmp_path / "install.log"
    log.write_text('temporary failure in name resolution\n')
    with pytest.raises(RuntimeError) as caught:
        setup.run_download_command([sys.executable, "-c", "raise PermissionError('read-only target')"], log)
    assert not setup.is_network_error(caught.value)


def test_running_parent_script_is_found_between_downloader_attempts(tmp_path):
    setup = _setup()
    script = tmp_path / "wan-download.sh"
    script.write_text("sleep 30 &\nwait\n")
    child = subprocess.Popen(["bash", str(script)], start_new_session=True)
    try:
        assert child.pid in setup.download_script_processes(script)
        other = tmp_path / "other" / "wan-download.sh"
        assert setup.download_script_processes(other) == []
    finally:
        os.killpg(child.pid, signal.SIGTERM)
        child.wait(timeout=5)
