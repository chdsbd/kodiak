import asyncio
from pathlib import Path

import click
import requests

from kodiak import app_config as conf
from kodiak.config import V1
from kodiak.queries import generate_jwt, get_token_for_install


@click.group()
def cli() -> None:
    pass


@cli.command(help="create a JWT for testing GitHub API endpoints")
def create_jwt() -> None:
    click.echo(
        generate_jwt(private_key=conf.PRIVATE_KEY, app_identifier=conf.GITHUB_APP_ID)
    )


@cli.command(help="generate the JSON schema for the .kodiak.toml")
def gen_conf_json_schema() -> None:
    click.echo(V1.schema_json(indent=2))


@cli.command(help="list all installs for the Kodiak GitHub App")
def list_installs() -> None:
    app_token = generate_jwt(
        private_key=conf.PRIVATE_KEY, app_identifier=conf.GITHUB_APP_ID
    )
    res = requests.get(
        "https://api.github.com/app/installations",
        headers=dict(
            Accept="application/vnd.github.machine-man-preview+json",
            Authorization=f"Bearer {app_token}",
        ),
    )

    if res.links:
        click.echo("pagination available")

    for r in res.json():
        try:
            install_url = r["account"]["html_url"]
            install_id = r["id"]
            click.echo(f"install:{install_id} for {install_url}")
        except (KeyError, IndexError):
            pass


@cli.command(help="fetches the OAuth token for a given install id")
@click.argument("install_id")
def token_for_install(install_id: str) -> None:
    """
    outputs the OAuth token for a given installation id.
    This is useful to help debug installation problems
    """
    token = asyncio.run(get_token_for_install(installation_id=install_id))
    click.echo(token)


@cli.command(help="prints out kodiak's view of a .kodiak.toml")
@click.argument("config_path", type=click.Path(exists=True))
def validate_config(config_path: str) -> None:
    """
    parse and output the json representation of a Kodiak config
    """
    cfg_text = Path(config_path).read_text()
    cfg_file = V1.parse_toml(cfg_text)
    assert isinstance(cfg_file, V1)
    click.echo(cfg_file.json(indent=2))
