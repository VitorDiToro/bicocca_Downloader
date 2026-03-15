import pytest
from pathlib import Path
from app.parsers import parse_yaml_file, parse_txt_file
from app.models import DownloadItem

FIXTURES = Path(__file__).parent / "fixtures"


class TestParseYamlFile:
    def test_returns_disciplina_and_items(self):
        disciplina, items = parse_yaml_file(FIXTURES / "valid.yaml")
        assert disciplina == "Curso de Exemplo"
        assert len(items) == 2

    def test_items_are_download_items(self):
        _, items = parse_yaml_file(FIXTURES / "valid.yaml")
        assert all(isinstance(i, DownloadItem) for i in items)

    def test_item_fields_are_mapped(self):
        _, items = parse_yaml_file(FIXTURES / "valid.yaml")
        assert items[0].url == "https://exemplo.com/video1"
        assert items[0].custom_name == "Aula 01 - Introdução"

    def test_raises_on_missing_url(self):
        with pytest.raises(ValueError, match="url"):
            parse_yaml_file(FIXTURES / "missing_url.yaml")

    def test_raises_if_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_yaml_file(FIXTURES / "nonexistent.yaml")

    def test_raises_if_pyyaml_missing(self, monkeypatch):
        import builtins
        real_import = builtins.__import__
        def mock_import(name, *args, **kwargs):
            if name == 'yaml':
                raise ImportError("No module named 'yaml'")
            return real_import(name, *args, **kwargs)
        monkeypatch.setattr(builtins, '__import__', mock_import)
        with pytest.raises(ImportError, match="pip install pyyaml"):
            parse_yaml_file(FIXTURES / "valid.yaml")


class TestParseTxtFile:
    def test_returns_list_of_download_items(self):
        items = parse_txt_file(FIXTURES / "urls.txt")
        assert len(items) == 3  # blank lines skipped

    def test_items_have_no_custom_name(self):
        items = parse_txt_file(FIXTURES / "urls.txt")
        assert all(i.custom_name is None for i in items)

    def test_urls_are_stripped(self):
        items = parse_txt_file(FIXTURES / "urls.txt")
        assert items[0].url == "https://exemplo.com/video1"

    def test_raises_if_file_empty(self, tmp_path):
        empty = tmp_path / "empty.txt"
        empty.write_text("")
        with pytest.raises(ValueError, match="vazio"):
            parse_txt_file(empty)

    def test_raises_if_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_txt_file(Path("nonexistent.txt"))
