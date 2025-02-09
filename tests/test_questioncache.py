import pathlib

from click.testing import CliRunner
import llm
from llm.cli import cli


TEST_USER_DIR = pathlib.Path(__file__).parent.parent / "test-llm-user-dir"
TEST_USER_DIR.mkdir(exist_ok=True)

# This model is just 30MB
# Originally from:
# https://huggingface.co/mixedbread-ai/mxbai-embed-xsmall-v1/tree/main/gguf
EMBED_URL = (
    "https://raw.githubusercontent.com/simonw/test-files-for-llm-gguf/refs/"
    "heads/main/mxbai-embed-xsmall-v1-q8_0.gguf"
)

EMBED_MODEL = ""


def _ensure_embed_model(runner):
    model_path = TEST_USER_DIR / "gguf" / "models" / "mxbai-embed-xsmall-v1-q8_0.gguf"
    if not model_path.exists():
        result = runner.invoke(cli, ["gguf", "download-embed-model", EMBED_URL])
        assert result.exit_code == 0


def _set_default_models():
    llm.set_default_model("SmolLM2")
    llm.set_default_embedding_model("gguf/mxbai-embed-xsmall-v1-q8_0")


def test_questioncache(monkeypatch):
    monkeypatch.setenv("LLM_USER_PATH", str(TEST_USER_DIR))
    runner = CliRunner(mix_stderr=False)
    _ensure_embed_model(runner)
    _set_default_models()

    result = runner.invoke(cli, ["questioncache", "clearcache", "--yes"])
    assert result.exit_code == 0

    question = "what's the difference between a duck"
    # Ask a first time
    result = runner.invoke(cli, ["questioncache", "ask", question])
    assert result.exit_code == 0
    assert question in result.stdout

    # Ask a second time
    result = runner.invoke(cli, ["questioncache", "ask", question])
    assert result.exit_code == 0
    assert question in result.stdout
    assert "Cached Answer 1" in result.stdout
