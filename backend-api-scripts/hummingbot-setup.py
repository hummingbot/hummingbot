import os
import shutil
import subprocess
import sys

import config as cfg


def ask_for_local_or_clone(repo_name, default_clone_url, target_dir):
    """
    Ask the user whether to use a local directory or clone the repository.
    """
    print(f"Do you have a local version of '{repo_name}'? (y/n)")
    response = input().strip().lower()

    if response == "y":
        path = input(f"Enter the local path to '{repo_name}': ").strip()
        if not os.path.exists(path):
            print("The specified path does not exist. Exiting.")
            sys.exit(1)
        print(f"Using local version of '{repo_name}' from {path}")
        shutil.copytree(path, target_dir, dirs_exist_ok=True)
    else:
        print(f"Cloning '{repo_name}' into {target_dir}")
        subprocess.run(["git", "clone", default_clone_url, target_dir], check=True)

def modify_environment_yaml(file_path, repo_url):
    """
    Modify the 'environment.yml' file to replace '- hummingbot' with the SSH repo URL.
    """
    if not os.path.exists(file_path):
        print(f"File '{file_path}' not found. Exiting.")
        sys.exit(1)

    with open(file_path, "r") as f:
        lines = f.readlines()

    with open(file_path, "w") as f:
        for line in lines:
            if "- hummingbot" in line:
                f.write(f"- {repo_url}\n")
            else:
                f.write(line)

def copy_custom_connectors(config_connectors, hummingbot_dir, backend_api_dir):
    """
    Copy custom connectors from the hummingbot repo to the backend-api directory.
    """
    for connector in config_connectors:
        source_path = os.path.join(hummingbot_dir, "connector", "exchange", connector)
        target_path = os.path.join(backend_api_dir, "custom-connectors", connector)

        if not os.path.exists(source_path):
            print(f"Custom connector '{connector}' not found in {source_path}. Skipping.")
            continue

        print(f"Copying '{connector}' from {source_path} to {target_path}")
        shutil.copytree(source_path, target_path, dirs_exist_ok=True)

def main():
    config = cfg.config

    # Step 1: Clone or use local hummingbot-backend-api
    backend_api_target_dir = os.path.join(".", "hummingbot", "backend-api")
    backend_api_repo = "https://github.com/hummingbot/backend-api.git"
    os.makedirs(backend_api_target_dir, exist_ok=True)

    ask_for_local_or_clone(
        repo_name="hummingbot-backend-api",
        default_clone_url=backend_api_repo,
        target_dir=backend_api_target_dir,
    )

    # Step 2: Clone or use local customized hummingbot repo
    hummingbot_target_dir = os.path.join(".", "hummingbot", "hummingbot")
    hummingbot_repo = config["hummingbot_repo"]
    os.makedirs(hummingbot_target_dir, exist_ok=True)

    ask_for_local_or_clone(
        repo_name="customized hummingbot",
        default_clone_url=hummingbot_repo,
        target_dir=hummingbot_target_dir,
    )

    # Step 3: Modify environment.yml in backend-api
    environment_yaml_path = os.path.join(backend_api_target_dir, "environment.yml")
    modify_environment_yaml(environment_yaml_path, config["hummingbot_repo"])

    # Step 4: Copy custom connectors
    copy_custom_connectors(
        config_connectors=config["custom_connectors"],
        hummingbot_dir=os.path.join(hummingbot_target_dir, "connector", "exchange"),
        backend_api_dir=os.path.join(backend_api_target_dir),
    )

    print("\nSetup complete! All repositories are ready and custom connectors have been copied.")

if __name__ == "__main__":
    main()
