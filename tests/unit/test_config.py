from pathlib import Path

import pytest

from ai_qa_engineering.config import ConfigError, EvidencePolicy, load_config


@pytest.mark.unit
def test_loads_example_configuration() -> None:
    config = load_config(Path("configs/example.yaml"))

    assert config.project.name == "demo-ai-app"
    assert str(config.project.base_url) == "https://example.com/"
    assert config.browser.profiles["desktop-chromium"].engine == "chromium"
    assert config.artifacts.screenshot is EvidencePolicy.ON_FAILURE
    assert [flow.id for flow in config.critical_flows] == ["AUTH-001", "AUTH-002"]


@pytest.mark.unit
def test_rejects_an_invalid_base_url(tmp_path: Path) -> None:
    config_file = tmp_path / "invalid.yaml"
    config_file.write_text(
        Path("configs/example.yaml")
        .read_text(encoding="utf-8")
        .replace("https://example.com", "example.com"),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="base_url"):
        load_config(config_file)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("original", "unsafe"),
    [("tests/example_project", "../outside"), ("artifacts/runs", "/tmp/runs")],
)
def test_rejects_unsafe_configured_paths(tmp_path: Path, original: str, unsafe: str) -> None:
    config_file = tmp_path / "invalid.yaml"
    config_file.write_text(
        Path("configs/example.yaml").read_text(encoding="utf-8").replace(original, unsafe),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="safe path"):
        load_config(config_file)


@pytest.mark.unit
def test_rejects_duplicate_critical_flow_ids(tmp_path: Path) -> None:
    config_file = tmp_path / "invalid.yaml"
    content = Path("configs/example.yaml").read_text(encoding="utf-8")
    config_file.write_text(content.replace("AUTH-002", "AUTH-001"), encoding="utf-8")

    with pytest.raises(ConfigError, match="unique"):
        load_config(config_file)
