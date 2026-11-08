# Local Development

This guide covers starting the development backend and HTTPS proxy with a
separate local Home Assistant instance. Do not use your primary heating system
for write tests.

## Prepare the Environment

Prerequisites: Python 3.14, Git, Homebrew, and a test Home Assistant instance
reachable at `http://127.0.0.1:8123`. Start HA separately from this repository;
the VS Code tasks in this project start only Caddy and the assistant.

In the test instance, install Versatile Thermostat, create a VTherm with
simulated sensors and an actuator, then install and configure Home Assistant's
**Model Context Protocol** integration. Publish the VTherm tools needed through
MCP and expose the test climate to Assist. Create a long-lived token with a test
administrator account; enter it in the UI, not in a configuration file.

From the repository root:

```sh
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m playwright install chromium
```

On Apple Silicon Macs, use ARM64 Python and dependencies. If your terminal is
running under Rosetta, open a native shell with `arch -arm64 /bin/bash` before
creating the virtual environment.

## Start the Application and Proxy

In VS Code, open the Command Palette and choose
**Tasks: Run Task > VTherm: demarrer en local (HTTPS)**. The task starts in
parallel:

- the backend on `127.0.0.1:8765`, available at `https://localhost:8443`;
- the Caddy proxy and its Home Assistant route,
  `https://localhost:8444` to `http://127.0.0.1:8123`.

On the first run, once the proxy is running, also run the
**VTherm: approuver le certificat local** task. macOS may request permission
or a password; enter it directly in the terminal. The task adds Caddy's local
certificate authority to the system keychain; it is not run automatically.
Then open `https://localhost:8443`.

If Home Assistant rejects proxied requests, configure **Trust X-Forwarded-For**
and **Trusted proxies** with the proxy address as shown in the HA logs. Set the
appropriate internal/external browser URL to `https://localhost:8444`. Do not
disable TLS verification or expose these ports to the Internet.

The tasks use separate standalone data storage:
`~/.local/share/vtherm-assistant-realtest`. Local development does not modify
the HA OS app options. In the assistant settings, configure the provider,
model, optional key, and test account's MCP token.

To stop the proxy and backend, use **Tasks: Terminate Task** and stop both
child tasks. Stop the HA instance separately using the method you used to
start it.

## Verify the Workflow

1. Sign in with a test administrator and verify the model and MCP connection.
2. Start a new conversation and compare a VTherm's inventory, state, and
   diagnosis with the information shown in HA.
3. Check that plugins, logs, and history are reported only when the integration
   publishes the corresponding tools.
4. To test a write, use a simulated thermostat only: check the target and every
   argument in the confirmation request, reject it first, then approve a test
   request and verify the final state in HA.
5. Restart the backend and verify that the latest conversation resumes.
   **New conversation** should replace that session without deleting saved
   secrets.

Real personal data, identifiers, keys, and tokens must never be added to tests
or the repository. Automated suites use simulated providers, identities, and
MCP servers.

## Tests

Install the development dependencies, then run the suites in two separate
pytest processes:

```sh
python -m pytest -q --ignore=tests/test_frontend.py --ignore=tests/test_packaging.py
python -m pytest -q tests/test_frontend.py tests/test_packaging.py
```

Browser tests use Chromium on desktop and mobile. Container tests require a
built image and `VTHERM_TEST_IMAGE`; see the [HA build guide](ha-app-build.md).
Without this variable, Docker tests are skipped.

Simulated tests do not prove compatibility with a real provider, HA/VTherm
version, or streaming through a real ingress. Record versions and results of
integrated tests separately.

French version: [development-fr](development-fr.md).