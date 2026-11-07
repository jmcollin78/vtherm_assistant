import argparse
import shutil
import tomllib
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
APP_FILES = (
    "config.yaml", "README.md", "DOCS.md", "CHANGELOG.md", "icon.png", "logo.png",
    "translations/fr.yaml", "translations/en.yaml",
)


def generate(output: Path) -> None:
    source = ROOT / "apps/vtherm_assistant"
    manifest = yaml.safe_load((source / "config.yaml").read_text())
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    if not isinstance(manifest, dict) or manifest.get("version") != version or not manifest.get("image"):
        raise ValueError("Invalid release metadata")
    sources = [(ROOT / "apps/repository.yaml", Path("repository.yaml"))]
    sources.extend((source / name, Path("vtherm_assistant") / name) for name in APP_FILES)
    if any(not path.is_file() or path.is_symlink() for path, _relative in sources):
        raise ValueError("Missing or linked release file")
    output.mkdir(parents=True, exist_ok=False)
    for path, relative in sources:
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare an unpublished HA app catalogue")
    parser.add_argument("--output", type=Path, default=ROOT / "dist/ha-app")
    options = parser.parse_args()
    try:
        generate(options.output)
    except (OSError, ValueError, KeyError, yaml.YAMLError):
        parser.exit(1, "Catalogue generation failed: check release metadata, source files and a new output directory.\n")
    print(f"Unpublished catalogue prepared: {options.output}")


if __name__ == "__main__":
    main()