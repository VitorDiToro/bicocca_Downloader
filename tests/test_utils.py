import pytest
from app.utils import sanitize_name, remove_ansi_codes, resolve_output_dir


class TestSanitizeName:
    def test_colon_becomes_space_dash(self):
        assert sanitize_name("Aula 1: Intro") == "Aula 1 - Intro"

    def test_invalid_windows_chars_become_underscore(self):
        assert sanitize_name('file<>"/\\|?*name') == "file________name"

    def test_trailing_dots_and_spaces_removed(self):
        assert sanitize_name("name. ") == "name"

    def test_empty_string_returns_sem_nome(self):
        assert sanitize_name("") == "sem_nome"

    def test_string_of_invalid_chars_returns_sem_nome(self):
        assert sanitize_name("...") == "sem_nome"

    def test_normal_name_unchanged(self):
        assert sanitize_name("Aula 01 - Democracia") == "Aula 01 - Democracia"


class TestRemoveAnsiCodes:
    def test_removes_color_codes(self):
        assert remove_ansi_codes("\x1b[32m100%\x1b[0m") == "100%"

    def test_string_without_codes_unchanged(self):
        assert remove_ansi_codes("plain text") == "plain text"

    def test_empty_string(self):
        assert remove_ansi_codes("") == ""

    def test_multiple_codes(self):
        assert remove_ansi_codes("\x1b[1m\x1b[32mBold Green\x1b[0m") == "Bold Green"


class TestResolveOutputDir:
    def test_returns_none_when_base_dir_is_none(self):
        assert resolve_output_dir(None, "single", None) is None

    def test_returns_none_when_base_dir_is_empty_string(self):
        assert resolve_output_dir("", "yaml", "Disciplina X") is None

    def test_single_mode_returns_path_of_base_dir(self, tmp_path):
        result = resolve_output_dir(str(tmp_path), "single", None)
        assert result == tmp_path

    def test_file_mode_returns_path_of_base_dir(self, tmp_path):
        result = resolve_output_dir(str(tmp_path), "file", None)
        assert result == tmp_path

    def test_yaml_mode_appends_sanitized_disciplina_as_subdir(self, tmp_path):
        result = resolve_output_dir(str(tmp_path), "yaml", "Democracia: poder popular")
        assert result == tmp_path / "Democracia - poder popular"

    def test_yaml_mode_without_disciplina_returns_base(self, tmp_path):
        result = resolve_output_dir(str(tmp_path), "yaml", None)
        assert result == tmp_path

    def test_returns_none_when_base_dir_is_whitespace_only(self):
        assert resolve_output_dir("   ", "single", None) is None
