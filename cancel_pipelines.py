#!/usr/bin/env python3

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import quote

import requests

from goodconf import GoodConf, Value
from goodconf.values import RequiredValueMissing


class Config(GoodConf):
    BASE_URL = Value(default="https://gitlab.com")
    USERNAME = Value(help="Gitlab username")
    AUTH_TOKEN = Value(
        help=(
            "Gitlab auth token with 'api' scope."
            "\nGo to /profile/personal_access_tokens to get one."
        )
    )


def load_config():
    config_home = os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
    config_path = Path(config_home) / "gitlab_cancel_pipelines.yml"
    config = Config(default_files=[config_path])
    try:
        config.load()
    except RequiredValueMissing as e:
        print(
            f"Missing required config value: {e.args[0]}",
            f"Set this value in environment or in {config_path}",
            "Example config file:",
            "#" * 15,
            config.generate_yaml(),
            sep="\n",
        )
    else:
        return config


def main():
    parser = argparse.ArgumentParser(
        description="Cancel all Gitlab pipelines of a user."
    )
    parser.add_argument(
        "project_path", help="Project path, such as: somegroup/someproject"
    )
    parser.add_argument("--dry-run", action="store_true")
    options = parser.parse_args()
    config = load_config()
    if not config:
        return 1
    token = config.AUTH_TOKEN
    sess = requests.Session()
    sess.headers["Authorization"] = f"Bearer {token}"

    encoded_path = quote(options.project_path, safe="")
    pipelines_url = f"{config.BASE_URL}/api/v4/projects/{encoded_path}/pipelines"
    response = sess.get(pipelines_url)
    response.raise_for_status()
    pipeline_cancelled = False
    for pipeline in response.json():
        if pipeline["status"] in ("pending", "running"):
            pipeline_url = f"{pipelines_url}/{pipeline['id']}"
            response = sess.get(pipeline_url)
            response.raise_for_status()
            data = response.json()
            if data.get("user", {}).get("username") == config.USERNAME:
                print(f"Cancelling pipeline #{data['id']} ...")
                if not options.dry_run:
                    response = sess.post(f"{pipeline_url}/cancel")
                    response.raise_for_status()
                pipeline_cancelled = True
    if not pipeline_cancelled:
        print("No pipeline to cancel.")


if __name__ == "__main__":
    sys.exit(main())
