import base64
import json
import os
import queue
import subprocess
import sys
import threading
import time
import tomllib
import uuid
from pathlib import Path
from unittest.mock import Mock, call, patch

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_ci_prepares_without_publishing():
    workflow = yaml.safe_load((ROOT / ".github/workflows/ha-app.yml").read_text())
    assert set(workflow["on"]) == {"push", "pull_request", "workflow_dispatch"}
    assert workflow["permissions"] == {"contents": "read"}
    job = workflow["jobs"]["verify"]
    assert job["env"]["VTHERM_TEST_IMAGE"] == "vtherm-assistant:ci"
    actions = {step["uses"] for step in job["steps"] if "uses" in step}
    assert {"docker/setup-docker-action@v5", "docker/setup-qemu-action@v4",
            "docker/setup-buildx-action@v4", "actions/upload-artifact@v7"} <= actions
    commands = "\n".join(step["run"] for step in job["steps"] if "run" in step)
    assert "--platform linux/arm64,linux/amd64 --load -t vtherm-assistant:ci ." in commands
    assert "python -m pytest -q" in commands
    assert "--ignore=tests/test_frontend.py --ignore=tests/test_packaging.py" in commands
    assert "python -m pytest -q tests/test_frontend.py tests/test_packaging.py" in commands
    assert "python scripts/package_ha_app.py" in commands
    assert "--push" not in commands and "git push" not in commands
    assert not any("login-action" in action for action in actions)


def test_catalogue_generation_is_clean(tmp_path, manifest):
    output = tmp_path / "catalogue"
    subprocess.run([sys.executable, str(ROOT / "scripts/package_ha_app.py"), "--output", str(output)],
                   check=True, capture_output=True, text=True, timeout=30)
    expected = {
        "repository.yaml", "vtherm_assistant/config.yaml", "vtherm_assistant/README.md",
        "vtherm_assistant/DOCS.md", "vtherm_assistant/CHANGELOG.md", "vtherm_assistant/icon.png",
        "vtherm_assistant/logo.png", "vtherm_assistant/translations/fr.yaml",
        "vtherm_assistant/translations/en.yaml",
    }
    assert {str(path.relative_to(output)) for path in output.rglob("*") if path.is_file()} == expected
    assert [str(path.relative_to(output)) for path in output.rglob("config.yaml")] == ["vtherm_assistant/config.yaml"]
    assert yaml.safe_load((output / "vtherm_assistant/config.yaml").read_text()) == manifest
    repository = yaml.safe_load((output / "repository.yaml").read_text())
    assert set(repository) == {"name", "url", "maintainer"}
    assert repository["url"] == manifest["url"]
    subprocess.run(["git", "check-ignore", "dist/ha-app"], cwd=ROOT,
                   check=True, capture_output=True, timeout=10)


def test_catalogue_generation_does_not_overwrite_existing_files(tmp_path):
    output = tmp_path / "catalogue"
    output.mkdir()
    marker = output / "user-content.txt"
    marker.write_text("retain-user-content")
    result = subprocess.run([sys.executable, str(ROOT / "scripts/package_ha_app.py"), "--output", str(output)],
                            check=False, capture_output=True, text=True, timeout=30)
    assert result.returncode != 0
    assert marker.read_text() == "retain-user-content"
    assert list(output.iterdir()) == [marker]


def test_app_documents_and_translations(manifest):
    directory = ROOT / "apps/vtherm_assistant"
    for name in ("README.md", "DOCS.md", "CHANGELOG.md"):
        assert (directory / name).read_text().strip()
    assert manifest["version"] in (directory / "CHANGELOG.md").read_text()
    for locale in ("fr", "en"):
        translation = yaml.safe_load((directory / "translations" / (locale + ".yaml")).read_text())
        assert set(translation) == {"configuration"}
        assert set(translation["configuration"]) == set(manifest["options"])
        for option in translation["configuration"].values():
            assert set(option) == {"name", "description"}
            assert all(isinstance(value, str) and value.strip() for value in option.values())


@pytest.mark.parametrize("name", ["icon.png", "logo.png"])
def test_app_brand_assets_decode(page, name):
    content = (ROOT / "apps/vtherm_assistant" / name).read_bytes()
    assert content == (ROOT / "brand" / name).read_bytes()
    source = "data:image/png;base64," + base64.b64encode(content).decode("ascii")
    dimensions = page.evaluate('''async (source) => {
        const image = new Image();
        image.src = source;
        await image.decode();
        return [image.naturalWidth, image.naturalHeight];
    }''', source)
    assert all(dimension > 0 for dimension in dimensions)


@pytest.fixture(name="manifest")
def app_manifest():
    return yaml.safe_load((ROOT / "apps/vtherm_assistant/config.yaml").read_text())


def test_app_manifest(manifest):
    assert set(manifest) == {
        "name", "version", "slug", "description", "url", "image", "arch",
        "startup", "boot", "init", "stage", "ingress", "ingress_port",
        "panel_admin", "panel_title", "panel_icon", "homeassistant_api",
        "backup", "environment", "options", "schema",
    }
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    assert manifest["version"] == version
    assert manifest["slug"] == "vtherm_assistant"
    assert manifest["image"] == "ghcr.io/jmcollin78/vtherm-assistant"
    assert manifest["url"] == "https://github.com/jmcollin78/vtherm_assistant"
    assert manifest["startup"] == "application"
    assert manifest["boot"] == "auto"
    assert manifest["stage"] == "experimental"
    assert manifest["ingress"] is True
    assert type(manifest["ingress_port"]) is int and manifest["ingress_port"] == 8099
    assert manifest["panel_admin"] is True
    assert manifest["homeassistant_api"] is True
    assert manifest["panel_icon"] == "mdi:thermostat"
    assert manifest["panel_title"] == manifest["name"] == "Assistant VTherm"
    assert isinstance(manifest["description"], str) and manifest["description"]
    assert set(manifest["arch"]) == {"aarch64", "amd64"}
    assert manifest["init"] is True
    assert manifest["backup"] == "cold"
    assert manifest["options"] == {"ha_internal_url": "http://homeassistant:8123"}
    assert manifest["schema"] == {"ha_internal_url": "url"}
    assert manifest["environment"] == {
        "VTHERM_DEPLOYMENT_MODE": "ingress", "VTHERM_DATA_DIR": "/data/vtherm-assistant",
    }


def test_manifest_launch_options(manifest, tmp_path, monkeypatch):
    from vtherm_assistant.__main__ import _configure_ingress, main

    options_path = tmp_path / "options.json"
    options_path.write_text(json.dumps(manifest["options"]))
    for name, value in manifest["environment"].items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("SUPERVISOR_TOKEN", "FAKE_SUPERVISOR_TOKEN")
    monkeypatch.setenv("VTHERM_HA_INTERNAL_URL", "http://previous:8123")

    def check_configuration(*_args, **_kwargs):
        assert os.environ["VTHERM_HA_INTERNAL_URL"] == "http://homeassistant:8123/"

    with patch("vtherm_assistant.__main__._configure_ingress",
               side_effect=lambda: _configure_ingress(options_path)), \
         patch("vtherm_assistant.__main__.uvicorn.run", side_effect=check_configuration) as run:
        main()
    run.assert_called_once_with("vtherm_assistant.main:app", host="0.0.0.0", port=8099,
                                proxy_headers=False, access_log=False)


@pytest.fixture(name="image", params=["linux/arm64", "linux/amd64"])
def docker_image(request):
    name = os.environ.get("VTHERM_TEST_IMAGE")
    if not name:
        pytest.skip("Set VTHERM_TEST_IMAGE to run the Docker checks")
    return name, request.param


def docker(*arguments, script=None, check=True):
    return subprocess.run(
        ["docker", *arguments], input=script, text=True, capture_output=True,
        check=check, timeout=120,
    )


def wait_for_server(container):
    lines = queue.Queue()
    process = subprocess.Popen(
        ["docker", "logs", "--follow", container],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )

    def collect():
        for line in process.stdout:
            lines.put(line)
        lines.put(None)

    reader = threading.Thread(target=collect, daemon=True)
    reader.start()
    deadline = time.monotonic() + 120
    try:
        while (remaining := deadline - time.monotonic()) > 0:
            try:
                line = lines.get(timeout=remaining)
            except queue.Empty:
                break
            assert line is not None, "Container exited before server startup"
            if "Uvicorn running on http://0.0.0.0:8099" in line:
                return
        pytest.fail("Container did not start within 120 seconds")
    finally:
        process.terminate()
        process.wait(timeout=10)
        reader.join(timeout=10)


def test_wait_for_server_uses_one_startup_deadline():
    lines = Mock()
    lines.get.side_effect = ["Initializing application\n", "Uvicorn running on http://0.0.0.0:8099\n"]
    process = Mock()
    reader = Mock()
    with patch("queue.Queue", return_value=lines), \
         patch("subprocess.Popen", return_value=process), \
         patch("threading.Thread", return_value=reader), \
         patch("time.monotonic", side_effect=[100, 145, 165]):
        wait_for_server("vtherm-test-startup")
    assert lines.get.call_args_list == [call(timeout=75), call(timeout=55)]
    process.terminate.assert_called_once_with()
    process.wait.assert_called_once_with(timeout=10)
    reader.join.assert_called_once_with(timeout=10)


def test_wait_for_server_reports_startup_timeout():
    lines = Mock()
    lines.get.side_effect = queue.Empty
    process = Mock()
    reader = Mock()
    with patch("queue.Queue", return_value=lines), \
         patch("subprocess.Popen", return_value=process), \
         patch("threading.Thread", return_value=reader), \
         patch("time.monotonic", side_effect=[100, 110]):
        with pytest.raises(pytest.fail.Exception, match="Container did not start within 120 seconds"):
            wait_for_server("vtherm-test-timeout")
    process.terminate.assert_called_once_with()
    process.wait.assert_called_once_with(timeout=10)
    reader.join.assert_called_once_with(timeout=10)


def test_image_dependencies_and_resources(image, manifest):
    name, platform = image
    config = json.loads(docker("image", "inspect", "--platform", platform,
                              "--format", "{{json .Config}}", name).stdout)
    labels = config["Labels"]
    assert config["Cmd"] == ["python", "-m", "vtherm_assistant"]
    assert config["User"] == "0:0"
    assert set(config["ExposedPorts"]) == {"8099/tcp"}
    environment = dict(value.split("=", 1) for value in config["Env"])
    assert all(environment[name] == value for name, value in manifest["environment"].items())
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    assert labels["org.opencontainers.image.version"] == version
    result = docker("run", "--rm", "--platform", platform, "-i", name, "python", "-", script='''
from importlib.metadata import distributions
from importlib.resources import files
from pathlib import Path
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from google.adk.agents import LlmAgent
import vtherm_assistant.main
inventory = Path("/usr/local/share/vtherm-assistant")
constraints = {canonicalize_name(requirement.name): requirement.specifier
               for requirement in map(Requirement, (inventory / "requirements-ha.lock").read_text().splitlines())}
for distribution in distributions():
    name = canonicalize_name(distribution.metadata["Name"])
    assert name in {"pip", "vtherm-assistant"} or distribution.version in constraints[name]
frontend = files("vtherm_assistant") / "frontend"
assert (frontend / "index.html").is_file()
assert (frontend / "brand-logo.png").read_bytes().startswith(b"\\x89PNG\\r\\n\\x1a\\n")
assert (inventory / "python.txt").is_file()
assert (inventory / "debian.txt").is_file()
assert not Path("/build").exists()
''')
    assert result.returncode == 0
    assert "No broken requirements found" in docker(
        "run", "--rm", "--platform", platform, name, "python", "-m", "pip", "check",
    ).stdout


def test_image_volume_restart_and_sigterm(image):
    name, platform = image
    volume = "vtherm-test-" + uuid.uuid4().hex
    containers = []
    docker("volume", "create", volume)
    try:
        for attempt in range(2):
            container = "vtherm-test-" + uuid.uuid4().hex
            containers.append(container)
            startup_started = time.monotonic()
            docker("run", "--detach", "--init", "--platform", platform,
                   "--name", container, "--volume", volume + ":/data",
                   "-e", "VTHERM_HA_INTERNAL_URL=http://homeassistant:8123", name)
            wait_for_server(container)
            if attempt == 0:
                startup_seconds = time.monotonic() - startup_started
                size = docker("image", "inspect", "--platform", platform,
                              "--format", "{{.Size}}", name).stdout.strip()
                memory = docker("stats", "--no-stream", "--format", "{{.MemUsage}}", container).stdout.strip()
                print(json.dumps({"platform": platform, "size_bytes": int(size),
                                  "startup_seconds": round(startup_seconds, 2), "memory": memory}))
            docker("exec", "-i", container, "python", "-", script=f'''
import os
import stat
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen
from vtherm_assistant.storage import PrivateDatabase, SecretStore
assert os.getuid() == 0 and os.getgid() == 0
try:
    urlopen("http://127.0.0.1:8099/api/conversation", timeout=5)
    raise AssertionError("Direct private access accepted")
except HTTPError as error:
    assert error.code == 403
directory = Path("/data/vtherm-assistant")
store = SecretStore(PrivateDatabase(directory))
if {attempt} == 0:
    store.put("test-alice", "home_assistant", "FAKE_TOKEN_FOR_IMAGE_TEST")
assert store.get("test-alice", "home_assistant") == "FAKE_TOKEN_FOR_IMAGE_TEST"
assert store.get("test-bob", "home_assistant") is None
assert stat.S_IMODE(directory.stat().st_mode) == 0o700
assert stat.S_IMODE(store.database.database.stat().st_mode) == 0o600
''')
            started = time.monotonic()
            docker("stop", "--time", "10", container)
            assert time.monotonic() - started < 10
            state = json.loads(docker("inspect", "--format", "{{json .State}}", container).stdout)
            assert state["ExitCode"] in (0, 143)
            logs = docker("logs", container).stdout + docker("logs", container).stderr
            assert "Application shutdown complete" in logs
            assert "FAKE_TOKEN_FOR_IMAGE_TEST" not in logs
    finally:
        for container in containers:
            docker("rm", "--force", container, check=False)
        docker("volume", "rm", volume)


@pytest.mark.parametrize("target, problem", [
    ("directory", "mode"), ("directory", "owner"),
    ("database", "mode"), ("database", "owner"),
])
def test_image_refuses_unsafe_storage_without_repair(image, target, problem):
    name, platform = image
    docker("run", "--rm", "--platform", platform, "-i", name, "python", "-", script=f'''
import os
from pathlib import Path
from vtherm_assistant.storage import PrivateDatabase
directory = Path("/tmp/private-image-test")
directory.mkdir(mode=0o700)
database = directory / "conversations.sqlite3"
database.write_bytes(b"retain-this-content")
database.chmod(0o600)
target = {target!r}
path = directory if target == "directory" else database
if {problem!r} == "mode":
    path.chmod(0o777 if target == "directory" else 0o666)
else:
    os.chown(path, 1000, 1000)
before = path.stat()
try:
    PrivateDatabase(directory).connect()
    raise AssertionError("Unsafe storage accepted")
except PermissionError:
    pass
after = path.stat()
assert (after.st_uid, after.st_gid, after.st_mode) == (before.st_uid, before.st_gid, before.st_mode)
assert database.read_bytes() == b"retain-this-content"
''')