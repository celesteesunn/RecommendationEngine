from src.config import PROJECT_ROOT, load_config, project_path


def test_config_has_required_sections():
    config = load_config()
    for section in ("dataset", "paths", "split", "model", "evaluation", "serving"):
        assert section in config


def test_dataset_files_are_tabular_only():
    files = load_config()["dataset"]["files"]
    assert set(files) == {"transactions_train.csv", "customers.csv", "articles.csv"}


def test_project_path_is_inside_repo():
    raw_dir = project_path(load_config()["paths"]["raw_dir"])
    assert raw_dir.is_relative_to(PROJECT_ROOT)
