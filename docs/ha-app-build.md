# HA OS App Build

## Base Image and Dependency Resolution

The base image is `python:3.14.10-slim-trixie`, pinned by the multi-architecture
digest `sha256:af8a5aa14780025dbfbcfbc81bd8a91ebd87711dd5b0f48ed71090949dd7cb1d`.
Its upstream revision is `01dcc3d31fcd879f9af36e097bd96328a457f4bd`.
Release constraints are in `requirements-ha.lock`; they cover transitive
Python dependencies and the setuptools build backend. The public version ranges
in `pyproject.toml` remain unchanged.

The package is installed from `pyproject.toml`; it is not run from a copy of
the repository. The Docker build context excludes virtual environments, local
data, caches, and planning files. The final image does not include `/build`.

The image contains inventory files under
`/usr/local/share/vtherm-assistant/`:

- `requirements-ha.lock`: constraints used for the build.
- `python.txt`: installed Python versions, including the app and pip.
- `debian.txt`: system package versions in the Debian base image.

## Local Validation

On 2026-11-07, using Docker 29.9.2 on the Apple Silicon development Mac:

| Platform | Build | Application/ADK imports | HTML/PNG | Constraints and pip check |
| --- | --- | --- | --- | --- |
| linux/arm64 | passed | passed | present | valid |
| linux/amd64 | passed | passed | present | valid |

Observed Python version: 3.14.10; package version: 0.1.0. The amd64 test uses
the local engine's emulation. No dependency-locking build failures were
observed. This does not certify ingress, Supervisor permissions, real
streaming, updates, or restores on HA OS.

## Build and Verify

From the repository root, use Docker/Buildx and an engine able to run both
architectures (through emulation or native runners):

```sh
docker buildx build --platform linux/arm64,linux/amd64 --load -t vtherm-assistant:test .
VTHERM_TEST_IMAGE=vtherm-assistant:test python -m pytest -q -s tests/test_packaging.py
docker run --rm --platform linux/arm64 vtherm-assistant:test cat /usr/local/share/vtherm-assistant/python.txt
docker run --rm --platform linux/arm64 vtherm-assistant:test cat /usr/local/share/vtherm-assistant/debian.txt
```

Loading a multi-architecture image requires recent containerd image storage.
On the development Mac, replace `python` with `arch -arm64 .venv/bin/python`
in Python commands. Without `VTHERM_TEST_IMAGE`, Docker tests are skipped; a
regular pytest run is not proof of a Linux image build.

Tests use only fake identities and tokens, no host ports, and temporary
`vtherm-test-*` volumes. They check imports, resources and constraints, internal
port 8099, denial of direct HTTP access, volume persistence, `0700`/`0600`
permissions, ownership, no automatic repair, and graceful SIGTERM shutdown in
under 10 seconds. They also report uncompressed size, Docker memory, and startup
time.

## User and Data

The explicit account is UID/GID `0:0`, stable across versions, to use the
Supervisor-provided `/data` volume without `chown` or relaxed permissions. This
is not a non-root image. The app requests no extra privileges, Docker socket,
HA mounts, hardware, or host networking.

Only `/data/vtherm-assistant` contains application data. It is created with
private permissions, and its SQLite database belongs to the same UID. Insecure
storage is rejected without automatic deletion, `chown`, or `chmod`. Never use
personal Mac data for image tests. Secrets remain in plaintext in SQLite and
must also be protected in backups.

The command is `python -m vtherm_assistant`, with Supervisor init forwarding
signals. Tests use `docker run --init` and no S6/Bashio. If the options file is
absent in test volumes, the development ingress path outside Supervisor is
used; the real file is mandatory when a Supervisor token is present. Regressions
in options handling are covered by `tests/test_app.py`.

## Local Reference Measurements

Measured on 2026-11-07, with the local Docker engine limited to 1.924 GiB:

| Platform | Uncompressed size (bytes) | Startup memory | Startup time |
| --- | --- | --- | --- |
| linux/arm64 | 596279769 | 144.1 MiB | 1.68 s |
| linux/amd64 | 576513482 | 141.9 MiB | 2.85 s |

These measurements cover the server without inference or a real HA connection;
they are not an HA OS budget guarantee. A conversation and loaded model may
increase memory use. The amd64 test is emulated, so startup time is not a
performance comparison between HA hardware.

## Catalog and CI

The generator copies only `repository.yaml` and the app's eight public files,
including a single `config.yaml`. It does not copy source code, OpenSpec,
virtual environments, SQLite databases, or personal options. `dist/` is
ignored by Git, and an existing output directory is refused rather than
removed or overwritten.

```sh
python scripts/package_ha_app.py --output dist/ha-app-release
```

The `ha-app.yml` CI workflow runs tests and builds both architectures with
Buildx, QEMU, and containerd image storage for multi-architecture loading.
GitHub Actions syntax is checked with actionlint 1.7.7, pinned by tool image
digest; this check has also been run locally. Release constraints are applied
to tests as well. CI prepares an `ha-app-unpublished` artifact, with no GHCR
login, write permission, image push, commit, or catalog push. A user push of
source code may trigger validation, never implicit publication.

Backend and browser suites run in two pytest processes. Synchronous Playwright
keeps an event loop active during its session, which conflicts with backend
tests using `asyncio.run()` in the same process. No tests are removed: files
excluded from the first process are all run in the second, with Docker tests
enabled.

```sh
python -m pytest -q --ignore=tests/test_frontend.py --ignore=tests/test_packaging.py
VTHERM_TEST_IMAGE=vtherm-assistant:test python -m pytest -q tests/test_frontend.py tests/test_packaging.py
openspec validate package-ha-os-app --strict
```

Local report from 2026-11-07, using the commands above and both built Docker
images: 203 backend tests passed in 5.29 s and 80 browser, packaging, and Docker
tests passed in 80.39 s, for 283 total tests without a final exclusion.
Actionlint and `openspec validate package-ha-os-app --strict` also passed.
Dependency deprecation warnings are separate from test failures. An initial
single-process run failed because of the Playwright/asyncio event-loop conflict;
separate runs are the validated procedure.

This report covers simulated authentication, writes, isolation, disallowed MCP
tools, secrets, and provider errors. It does not prove a real Supervisor
session, or a read or restore on primary HA. The workflow was subsequently
pushed by the user. The GitHub API confirms success for
[run 42423430156](https://github.com/jmcollin78/vtherm_assistant/actions/runs/42423430156)
on source revision `bcb01602992bdcd9aa9b4b92b0229dd7c645f644`.

## Release 1.0.0

On 2026-11-08, source revision
`bbbaba2f8ad87099fc7f199886b46f5c0472f768` was published to `main`. The
[CI run 42531162871](https://github.com/jmcollin78/vtherm_assistant/actions/runs/42531162871)
passed on that exact revision. Package metadata, Docker version label, app
manifest, and changelog identify version `1.0.0`.

This release discovers accepted VTherm MCP tools dynamically and extends
diagnostics to plugin status, thermostat history and logs, linked entity states,
and official documentation when available. Every VTherm write requires
separate approval in the UI; generic Home Assistant writes remain unavailable.

The public image `ghcr.io/jmcollin78/vtherm-assistant:1.0.0` has index digest
`sha256:a789e6bfa2f13f2eca1797f662e9e6d935afafc6b0b410908ecf1b97a89aa512`.
Its arm64 and amd64 manifests carry version `1.0.0` and source revision
`bbbaba2f8ad87099fc7f199886b46f5c0472f768`. Both manifests, their
configurations, and all ten layers were downloaded anonymously; every size and
SHA-256 was verified. The published image passed all six platform-specific
Docker tests on each architecture.

The `ha-app` catalog was published at commit
`9b7ee8454a9a310ee01638c0b9e326565a67d352`, a descendant of the `0.1.2`
catalog commit. The manifest, README, DOCS, and changelog changed; all nine
public files match the validated snapshot byte for byte. An independent public
clone confirmed the published branch. The repository URL remains
`https://github.com/jmcollin78/vtherm_assistant#ha-app`.

The app remains at the experimental stage. New write workflows were not
deployed or validated on HA OS during publication. No HA configuration,
heating action, backup, or restore was performed.

## Release 0.1.2

On 2026-11-08, after explicit authorization for release commits and pushes,
source revision `8c37a5da0b88319692080f1ac59d5e7e9d196df1` was published to
`main`. It follows feature commit `a84da1ac807b3cf9c9b5f5438ee5e7c533271987`
and changes only the four version and changelog files. [CI run
42477520458](https://github.com/jmcollin78/vtherm_assistant/actions/runs/42477520458)
completed successfully on that exact revision.

This release delivered dynamic model catalogs with fallback suggestions and
manual entry, localized and persistent message timestamps, an initial MCP
inventory without model generation or duplicates on recovery, and safe Markdown
table rendering. Write tools remained disallowed; future discovery of all
VTherm tools was not included.

Local arm64 and amd64 builds passed. The two test processes validated 253
backend tests and 104 browser, packaging, and Docker tests, 357 passes total
with no Docker skips. The tested image labels for version, source, and revision
were checked; screenshots of the three new workflows on desktop and mobile
were reviewed.

The public image `ghcr.io/jmcollin78/vtherm-assistant:0.1.2` has digest
`sha256:909f495c15fc0e1972818c08601ea1e2a27ce11fee3ab833a93f46f3ffb0d43a`.
This index matches the locally tested image. Both manifests, configurations,
and all ten layers were downloaded anonymously, with sizes and SHA-256 values
verified; labels match the published source. Public digests for `0.1.0` and
`0.1.1` remain unchanged.

The `ha-app` catalog was published at commit
`d270d5906a270de2691ff058d63679d612af085d`, a descendant of the prior release.
Only the manifest and changelog changed; all nine public files were compared
byte-for-byte with the validated snapshot. The repository URL remains
`https://github.com/jmcollin78/vtherm_assistant#ha-app`.

On 2026-11-08, after deployment of `0.1.2` on HA OS, the user confirmed that
the three changes work: dynamic model catalogs, conversation date/time, and the
opening inventory. This is user-reported evidence of real operation, without
a network capture or exhaustive provider/error validation. Old messages with
unknown dates are not assigned invented timestamps; restoring an old
conversation does not insert the inventory among its messages. Starting a new
conversation replaces the current one. No HA configuration, exposure, heating
command, or backup was involved in publication. OpenSpec progress remains
37/55 for `add-vtherm-ai-assistant` and 21/25 for `package-ha-os-app`, with no
archival.

## Release 0.1.1

On 2026-11-08, source revision
`93bddd921656a5a02c4c94d20cf2a5b18a7d0252` passed [CI run
42464546539](https://github.com/jmcollin78/vtherm_assistant/actions/runs/42464546539).
The test helper now waits up to 120 seconds total for startup without renewing
the timeout for each log line; the SIGTERM limit remains 10 seconds.

This release accepts the three VTherm read tools with or without the
`assist__` prefix. HA preserves raw names when one LLM API is exposed and adds
a namespace when it merges several APIs. Write commands remain disallowed, and
schemas remain local.

The public image `ghcr.io/jmcollin78/vtherm-assistant:0.1.1` has digest
`sha256:50806a00247a57e865dab6597702adb8708ec8171554a58be898caf3fc10d9a6`.
The 12 Docker tests for the exact arm64 and amd64 images passed before
publication. The published index matches the tested index; both configurations
and all ten layers were downloaded anonymously, with sizes and SHA-256 values
verified. Version, source, and revision labels match this release. The public
digest for `0.1.0` is unchanged.

The `ha-app` catalog was published at commit
`6e3d983e89f710d1bc1433c8fb32ad8409018719`, preserving its history. All nine
public files were compared byte-for-byte with the validated catalog; only the
version manifest and changelog changed. Updating the app and performing a real
MCP read on HA OS still required verification. No HA configuration changed
during publication.

## Release 0.1.0 and HA OS Validation

On 2026-11-08, after explicit approval, image
`ghcr.io/jmcollin78/vtherm-assistant:0.1.0` was published and made public.
Multi-architecture index digest:
`sha256:1e706799da51a80d83cf39f32ed14123177d541978dc6be01dc0d5878fbeea8d`.

All 12 Docker tests for the release images passed. Published arm64 and amd64
manifests match the tested images; version, source, and revision labels were
verified. Pulls with anonymous Docker configuration succeeded. To rule out a
local-cache false positive, every configuration and layer for both platforms
was also downloaded directly from the anonymous registry, with size and
SHA-256 verified.

The catalog was published to branch `ha-app` at commit
`5cc3de833d08c81c4f125d76be02ecad90384888`. Public GitHub access confirmed the
exact nine expected files, identical to the validated catalog; no OpenSpec or
application source files are distributed. The source branch remained at its
original revision. Local documentation and OpenSpec tracking changes were not
committed to that branch.

Distribution uses only the `ha-app` branch. Add this URL to the store, keeping
the suffix: `https://github.com/jmcollin78/vtherm_assistant#ha-app`. The
Supervisor Git parser accepts the branch suffix. The user confirmed the catalog
loaded on the primary HA instance on 2026-11-08: it displayed only VTherm
Assistant, version `0.1.0`, experimental stage, with no false OpenSpec app.
Recorded user environment: Home Assistant OS, Core `2026.10.4`, Supervisor
`2026.10.5`, OS `18.4`, frontend `20260930.5`, amd64 container, and VTherm
`10.6.3`.

The user confirmed successful `0.1.0` installation, the
`ha_internal_url` value `http://homeassistant:8123`, a sidebar icon, and the
conversation page opening through real ingress. The server path for
administrator validation is corroborated by the existing code: ingress
`AccessMiddleware` protects all routes, including HTML and
`GET /api/conversation`; it requires Supervisor origin, a unique identity, and
a positive `verify_ingress_admin` result through
`ws://supervisor/core/websocket` and `config/auth/list`. Successful opening
confirms this chain for the current account, but does not establish rejection
of a different account. No raw network trace was collected.

No HA/VTherm update, heating change, or entity exposure change was needed.
MCP reads, real streaming, persistence after restart/update, real account
isolation, errors, and backup tests still needed verification at that stage.
The app remained experimental; this record did not certify full compatibility.

## Publication Procedure

These are separate release steps, not authorization to perform them:

1. Get explicit approval to commit and push source changes so the workflow is
	available on GitHub, then wait for its tests and builds to pass on that
	revision. Do not publish after a failure.
2. Verify package version, image label, manifest, and changelog consistency.
	Image tags are immutable; never overwrite a published version. Prove a new
	tag is absent before publishing; network or authentication failure does not
	prove absence.
3. Get explicit approval to publish to
	`ghcr.io/jmcollin78/vtherm-assistant:<version>`. Authenticate directly in
	the terminal with an account allowed to write this package; do not send a
	token to the assistant. Future publishing CI would require `packages: write`
	and explicit approval, neither of which the current workflow has.
4. Publish both architectures before the catalog. Only after approval and
	validation of a new tag, with `VERSION` set to that new version (never
	`0.1.0`, which is already published), for example:

	```sh
	docker buildx build --platform linux/arm64,linux/amd64 --push -t "ghcr.io/jmcollin78/vtherm-assistant:${VERSION:?define an approved new version}" .
	```

5. Make the GHCR package public in its settings. With a separate anonymous
	Docker configuration, verify each declared architecture, labels, and
	resources. A successful pull while logged in as the maintainer does not
	prove Supervisor can download the image.
6. Update publication status in the README/changelog, then regenerate the
	catalog in a new output directory. Get explicit approval before creating or
	pushing the `ha-app` branch with only its catalog contents, from a separate
	working directory. Do not switch branches in the user's working tree or
	delete source files there. Automated Git publication would need
	`contents: write`, not granted to current CI.
7. Verify the available tag, catalog version, single app, and distribution URL
	with Supervisor before documenting an effective installation link. Keep
	the experimental stage until real ingress, permissions, streaming, and
	restore evidence is available.

For subsequent releases, use a new immutable version, validate it, back up the
app after approval, publish the image first, and the catalog second. Do not
change heating, Recorder, Core, or OS. Installation, updates, and restores on
primary HA each require their own appropriate confirmation.

For later catalog releases, clone the existing `ha-app` branch to preserve its
history. Generate a valid new catalog, update only its nine public files, and
push without force. Do not merge the source branch into `ha-app`, which would
reintroduce OpenSpec files.

French version: [ha-app-build-fr](ha-app-build-fr.md).