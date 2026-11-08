# Contributing

Every contribution, including documentation changes, must be defined through
OpenSpec. A pull request is ready only when every task in its change is
completed, verified, and checked off, and strict OpenSpec validation passes.
Do not check a task to indicate an intention or substitute a simulated test for
a verification that the task requires.

## OpenSpec Workflow

OpenSpec describes requirements and changes in [`openspec/`](openspec/). See
[openspec.dev](https://openspec.dev/) and
[Fission-AI/OpenSpec](https://github.com/Fission-AI/OpenSpec) for installation
and reference material.

Common prompts available in configured assistants:

- `/opsx:explore`: clarify a need or compare options without changing code;
- `/opsx:propose <slug-and-request>`: create the proposal, specifications,
  design, and verifiable tasks;
- `/opsx:apply`: implement the accepted change's tasks and validate each step;
- `/opsx:archive`: archive a completed change and sync specifications after
  validation.

For each change, describe expected behavior, exclusions, and impacts on Home
Assistant, VTherm, MCP, providers, and data. Have the change reviewed before
expanding scope. Clearly distinguish real tests from simulated tests. A task
that cannot be completed or verified must remain open and be resolved before
PR approval; do not reduce scope midstream without agreement.

Before requesting review:

1. Complete every checkbox in `tasks.md` with the required evidence.
2. Run `openspec validate --all --strict` and resolve all errors.
3. Run the relevant tests. For the full suite, follow both commands in the
   [development guide](docs/development.md).
4. Update the README, HA documentation, translations, or changelog when user
   behavior changes.
5. Describe the change, risks, tests run, and remaining limitations in the PR.
   Every OpenSpec task must be complete for the PR to be approved.

## Repository Conventions

- Python application: `src/vtherm_assistant/`; frontend:
  `src/vtherm_assistant/frontend/`; tests: `tests/`; public HA OS app:
  `apps/vtherm_assistant/`.
- All Home Assistant reads and writes go through the official MCP server.
  Automated tests must use fake transports and data. Never include a token, API
  key, identifier, private conversation, or backup in a PR.
- Every VTherm write must explicitly confirm its target and arguments. Do not
  add generic HA commands, confirmation bypasses, or autonomous monitoring.
- Do not change real heating equipment to validate a change. Integrated write
  tests must use a simulated VTherm and separate user approval.
- Preserve secret redaction, strict storage permissions, and account
  boundaries. Do not log raw tool results, messages, or secrets.
- Image publication, updates to the `ha-app` catalog, releases, and operations
  on a real HA instance require explicit maintainer authorization. A PR does
  not trigger them.

## Pull Requests

Keep each PR scoped to its associated OpenSpec change. Tests must not depend on
an account, home network, or real API key. Report unverifiable checks instead
of presenting them as passing. Open OpenSpec tasks, tasks without evidence, or
failed strict validation mean the change is not complete.

French version: [CONTRIBUTING-fr](CONTRIBUTING-fr.md).