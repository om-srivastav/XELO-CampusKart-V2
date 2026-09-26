from click.testing import CliRunner
from support import Client

from app.cli import build_cli


def test_cli_initialization_and_health(app):
    runner = CliRunner()
    result = runner.invoke(build_cli(app.state.settings, app.state.session_factory), args=["seed-categories"])
    assert result.exit_code == 0, result.output
    assert (
        runner.invoke(
            build_cli(app.state.settings, app.state.session_factory),
            args=["campus-add", "Example College", "Kanpur", "--domains", "example.edu"],
        ).exit_code
        == 0
    )
    assert Client(app).get("/health/ready").status_code == 200


def test_public_safety_page(client):
    assert client.get("/safety").status_code == 200


def test_member_home_has_real_listing(client, people):
    from conftest import listing, login

    login(client)
    listing(client)
    response = client.get("/")
    assert b"Calculus textbook" in response.content
