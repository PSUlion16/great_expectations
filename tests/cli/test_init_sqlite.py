import os
import re
import shutil

import pytest
from click.testing import CliRunner
from sqlalchemy import create_engine

from great_expectations import DataContext
from great_expectations.cli import cli
from great_expectations.data_context.util import file_relative_path
from great_expectations.util import gen_directory_tree_str
from tests.cli.test_cli import yaml

@pytest.fixture
def titanic_sqlite_db_file():
    from sqlalchemy import create_engine
    titanic_db_path = file_relative_path(__file__, "../test_sets/titanic.db")
    engine = create_engine('sqlite:///{}'.format(titanic_db_path))
    assert engine.execute("select count(*) from titanic").fetchall()[0] == (1313,)
    return titanic_db_path



def test_cli_init_on_new_project(tmp_path_factory, titanic_sqlite_db_file):
    basedir = str(tmp_path_factory.mktemp("test_cli_init_diff"))

    database_path = os.path.join(basedir, "titanic.db")
    shutil.copy(titanic_sqlite_db_file, database_path)
    engine = create_engine('sqlite:///{}'.format(database_path))

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["init", "--no-view", "-d", basedir],
        input="Y\n2\n5\ntitanic\n{}\n1\nwarning\n\n".format(engine.url),
    )
    stdout = result.output
    print(stdout)

    assert len(stdout) < 3000, "CLI output is unreasonably long."

    assert "Always know what to expect from your data" in stdout
    assert "What data would you like Great Expectations to connect to" in stdout
    assert "Which database backend are you using" in stdout
    assert "Give your new data source a short name" in stdout
    assert "What is the url/connection string for the sqlalchemy connection" in stdout
    assert "Name the new expectation suite [warning]" in stdout
    assert (
        "Great Expectations will choose a couple of columns and generate expectations about them"
        in stdout
    )
    assert "Profiling main.titanic" in stdout
    assert "Building" in stdout
    assert "Data Docs" in stdout
    assert "A new Expectation suite 'warning' was added to your project" in stdout
    assert "Great Expectations is now set up" in stdout

    assert os.path.isdir(os.path.join(basedir, "great_expectations"))
    config_path = os.path.join(basedir, "great_expectations/great_expectations.yml")
    assert os.path.isfile(config_path)

    config = yaml.load(open(config_path, "r"))
    data_source_class = config["datasources"]["files_datasource"]["data_asset_type"][
        "class_name"
    ]
    assert data_source_class == "PandasDataset"

    obs_tree = gen_directory_tree_str(os.path.join(basedir, "great_expectations"))

    # Instead of monkey patching datetime, just regex out the time directories
    date_safe_obs_tree = re.sub(r"\d*T\d*\.\d*Z", "9999.9999", obs_tree)

    assert (
        date_safe_obs_tree
        == """\
great_expectations/
    .gitignore
    great_expectations.yml
    datasources/
    expectations/
        files_datasource/
            default/
                Titanic/
                    warning.json
    notebooks/
        pandas/
            create_expectations.ipynb
            validation_playground.ipynb
        spark/
            create_expectations.ipynb
            validation_playground.ipynb
        sql/
            create_expectations.ipynb
            validation_playground.ipynb
    plugins/
        custom_data_docs/
            renderers/
            styles/
                data_docs_custom_styles.css
            views/
    uncommitted/
        config_variables.yml
        data_docs/
            local_site/
                index.html
                expectations/
                    files_datasource/
                        default/
                            Titanic/
                                warning.html
                static/
                    fonts/
                        HKGrotesk/
                            HKGrotesk-Bold.otf
                            HKGrotesk-BoldItalic.otf
                            HKGrotesk-Italic.otf
                            HKGrotesk-Light.otf
                            HKGrotesk-LightItalic.otf
                            HKGrotesk-Medium.otf
                            HKGrotesk-MediumItalic.otf
                            HKGrotesk-Regular.otf
                            HKGrotesk-SemiBold.otf
                            HKGrotesk-SemiBoldItalic.otf
                    images/
                        0_values_not_null_html_en.jpg
                        10_suite_toc.jpeg
                        11_home_validation_results_failed.jpeg
                        12_validation_overview.png
                        13_validation_passed.jpeg
                        14_validation_failed.jpeg
                        15_validation_failed_unexpected_values.jpeg
                        16_validation_failed_unexpected_values (1).gif
                        1_values_not_null_html_de.jpg
                        2_values_not_null_json.jpg
                        3_values_not_null_validation_result_json.jpg
                        4_values_not_null_validation_result_html_en.jpg
                        5_home.png
                        6_home_tables.jpeg
                        7_home_suites.jpeg
                        8_home_validation_results_succeeded.jpeg
                        9_suite_overview.png
                        favicon.ico
                        glossary_scroller.gif
                        iterative-dev-loop.png
                        logo-long-vector.svg
                        logo-long.png
                        short-logo-vector.svg
                        short-logo.png
                        validation_failed_unexpected_values.gif
                        values_not_null_html_en.jpg
                        values_not_null_json.jpg
                        values_not_null_validation_result_html_en.jpg
                        values_not_null_validation_result_json.jpg
                    styles/
                        data_docs_custom_styles_template.css
                        data_docs_default_styles.css
                validations/
                    9999.9999/
                        files_datasource/
                            default/
                                Titanic/
                                    warning.html
        samples/
        validations/
            9999.9999/
                files_datasource/
                    default/
                        Titanic/
                            warning.json
"""
    )

    # This is important to make sure the user isn't seeing tracebacks
    assert "Traceback" not in stdout
    assert result.exit_code == 0


# TODO this test is failing because the behavior is broken
def test_init_on_existing_project_with_no_datasources_should_add_one(
    initialized_project,
):
    project_dir = initialized_project
    ge_dir = os.path.join(project_dir, DataContext.GE_DIR)

    _remove_all_datasources(ge_dir)

    runner = CliRunner()
    result = runner.invoke(
        cli, ["init", "--no-view", "-d", project_dir], input="1\n1\ndata\nmy_data_dir\n"
    )
    stdout = result.stdout
    print(stdout)

    assert result.exit_code == 0

    assert "Error: invalid input" not in stdout

    assert "Always know what to expect from your data" in stdout
    assert "What data would you like Great Expectations to connect to" in stdout
    assert "A new datasource 'my_data_dir' was added to your project" in stdout
    assert "Would you like to build & view this project's Data Docs" in stdout

    config = _load_config_file(os.path.join(ge_dir, DataContext.GE_YML))
    assert "my_data_dir" in config["datasources"].keys()

    # This is important to make sure the user isn't seeing tracebacks
    assert "Traceback" not in stdout


def _remove_all_datasources(ge_dir):
    config_path = os.path.join(ge_dir, DataContext.GE_YML)

    config = _load_config_file(config_path)
    config["datasources"] = {}

    with open(config_path, "w") as f:
        yaml.dump(config, f)

    context = DataContext(ge_dir)
    assert context.list_datasources() == []


def _load_config_file(config_path):
    assert os.path.isfile(config_path), "Config file is missing. Check path"

    with open(config_path, "r") as f:
        read = f.read()
        config = yaml.load(read)

    assert isinstance(config, dict)
    return config


@pytest.fixture
def initialized_project(tmp_path_factory):
    """This is an initialized project through the CLI."""
    basedir = str(tmp_path_factory.mktemp("my_rad_project"))
    os.makedirs(os.path.join(basedir, "data"))
    data_path = os.path.join(basedir, "data/Titanic.csv")
    fixture_path = file_relative_path(__file__, "../test_sets/Titanic.csv")
    shutil.copy(fixture_path, data_path)
    runner = CliRunner()
    _ = runner.invoke(
        cli,
        ["init", "--no-view", "-d", basedir],
        input="Y\n1\n1\n{}\n\n\n\n".format(data_path),
    )

    context = DataContext(os.path.join(basedir, DataContext.GE_DIR))
    assert isinstance(context, DataContext)
    assert len(context.list_datasources()) == 1
    return basedir


def test_init_on_existing_project_with_multiple_datasources_exist_do_nothing(
    initialized_project, filesystem_csv_2
):
    project_dir = initialized_project
    ge_dir = os.path.join(project_dir, DataContext.GE_DIR)

    context = DataContext(ge_dir)
    context.add_datasource(
        "another_datasource",
        module_name="great_expectations.datasource",
        class_name="PandasDatasource",
        base_directory=str(filesystem_csv_2),
    )
    assert len(context.list_datasources()) == 2

    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--no-view", "-d", project_dir], input="n\n")
    stdout = result.stdout

    assert result.exit_code == 0

    assert "Error: invalid input" not in stdout

    assert "Always know what to expect from your data" in stdout
    assert "This looks like an existing project that" in stdout
    assert "appears complete" in stdout
    assert "Would you like to build & view this project's Data Docs" in stdout

    # This is important to make sure the user isn't seeing tracebacks
    assert "Traceback" not in stdout


def test_init_on_existing_project_with_datasource_with_existing_suite_offer_to_build_docs(
    initialized_project,
):
    project_dir = initialized_project

    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--no-view", "-d", project_dir], input="n\n")
    stdout = result.stdout

    assert result.exit_code == 0

    assert "Error: invalid input" not in stdout

    assert "Always know what to expect from your data" in stdout
    assert "This looks like an existing project that" in stdout
    assert "appears complete" in stdout
    assert "Would you like to build & view this project's Data Docs" in stdout

    # This is important to make sure the user isn't seeing tracebacks
    assert "Traceback" not in stdout


def test_init_on_existing_project_with_datasource_with_no_suite_create_one(
    initialized_project,
):
    project_dir = initialized_project
    ge_dir = os.path.join(project_dir, DataContext.GE_DIR)
    uncommitted_dir = os.path.join(ge_dir, "uncommitted")

    # mangle the setup to remove all traces of any suite
    expectations_dir = os.path.join(ge_dir, "expectations")
    data_docs_dir = os.path.join(uncommitted_dir, "data_docs")
    validations_dir = os.path.join(uncommitted_dir, "validations")

    _delete_and_recreate_dir(expectations_dir)
    _delete_and_recreate_dir(data_docs_dir)
    _delete_and_recreate_dir(validations_dir)

    context = DataContext(ge_dir)
    assert context.list_expectation_suite_keys() == []

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["init", "--no-view", "-d", project_dir],
        input="{}\nsink_me\n\n\n".format(os.path.join(project_dir, "data/Titanic.csv")),
    )
    stdout = result.stdout

    assert result.exit_code == 0

    assert "Error: invalid input" not in stdout
    assert "Always know what to expect from your data" in stdout
    assert "Enter the path (relative or absolute) of a data file" in stdout
    assert "Profiling sink_me" in stdout
    assert "The following Data Docs sites were built" in stdout
    assert "Great Expectations is now set up" in stdout
    assert "A new Expectation suite 'warning' was added to your project" in stdout

    # This is important to make sure the user isn't seeing tracebacks
    assert "Traceback" not in stdout


def _delete_and_recreate_dir(directory):
    shutil.rmtree(directory)
    assert not os.path.isdir(directory)
    os.mkdir(directory)
    assert os.path.isdir(directory)
