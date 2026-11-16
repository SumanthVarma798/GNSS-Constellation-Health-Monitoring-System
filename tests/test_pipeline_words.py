"""Pipeline wording facts (evidence/pipeline_words.py) stay aligned with source files."""
import importlib
from pathlib import Path
import re

from evidence.pipeline_words import SETTING_SENTENCES, STAGES

ROOT = Path(__file__).resolve().parent.parent


def _normalize(text):
    # Workflows often use "\" line continuations and "$GITHUB_WORKSPACE/..." absolute paths.
    # Stage commands keep the same command in a shorter, repository-relative shape.
    text = re.sub(r'"\$GITHUB_WORKSPACE/([^"]+)"', r"\1", text)
    text = re.sub(r"\$GITHUB_WORKSPACE/([^\s]+)", r"\1", text)
    text = text.replace("\\", " ")
    return re.sub(r"\s+", " ", text).strip()


def _module(path):
    return importlib.import_module(path.removesuffix(".py").replace("/", "."))


def test_stage_commands_are_kept_in_sync_with_their_workflow_files():
    for stage_key, words in STAGES.items():
        technical = words["technical"]
        workflow_file = technical["workflow_file"]
        if not workflow_file:
            continue
        workflow_text = (ROOT / workflow_file).read_text(encoding="utf-8")
        normalized_workflow = _normalize(workflow_text)
        for command in technical["commands"]:
            # A note in brackets at the end says when the step runs; it is not part of the command.
            command = re.sub(r"\s+\([^()]*\)$", "", command)
            # archive.yml runs every group with --group "$GROUP"; the words name the group itself.
            if technical.get("schedule_group"):
                command = command.replace(f"--group {technical['schedule_group']}", '--group "$GROUP"')
            assert _normalize(command) in normalized_workflow, (stage_key, command)


def test_each_stage_setting_exists_in_one_of_its_named_setting_modules():
    module_cache = {}
    for stage_key, words in STAGES.items():
        technical = words["technical"]
        module_paths = technical["settings_files"]
        modules = [module_cache.setdefault(path, _module(path)) for path in module_paths]
        for setting_name in technical["settings"]:
            assert any(hasattr(module, setting_name) for module in modules), (stage_key, setting_name, module_paths)


def test_setting_sentence_keys_name_real_settings():
    module_paths = sorted({path for words in STAGES.values() for path in words["technical"]["settings_files"]})
    modules = [_module(path) for path in module_paths]
    for setting_name in SETTING_SENTENCES:
        assert any(hasattr(module, setting_name) for module in modules), setting_name
