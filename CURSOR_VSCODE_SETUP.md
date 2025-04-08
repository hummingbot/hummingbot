# VS Code/Cursor Setup Guide

## Required Files
1. `.env`:
```
PYTHONPATH=${PYTHONPATH}:${PWD}
CONDA_ENV=hummingbot
```

2. `.vscode/settings.json`:
```json
{
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": [
        "test",
        // "-v",  // optional: verbose output
        
        // From MakeFile (currently broken tests)
        "--ignore=test/hummingbot/connector/derivative/dydx_v4_perpetual/",
        "--ignore=test/hummingbot/connector/derivative/injective_v2_perpetual/",
        "--ignore=test/hummingbot/connector/exchange/injective_v2/",
        "--ignore=test/hummingbot/remote_iface/",
        "--ignore=test/connector/utilities/oms_connector/",
        "--ignore=test/hummingbot/strategy/amm_arb/",
        
        // Skip prompt tests that modify conf_client.yml
        "--ignore=test/hummingbot/client/command/test_create_command.py",
    ],
    "python.envFile": "${workspaceFolder}/.env"
}
```

3. `.vscode/launch.json`:
```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Hummingbot",
            "type": "debugpy",
            "request": "launch",
            "program": "${workspaceRoot}/bin/hummingbot.py",
            "console": "integratedTerminal"
        }
    ]
}
```

## Running Tests
1. Set conda hummingbot environment as the python interpreter
2. Go to Testing View (flask icon in sidebar)

## Notes on Ignored Tests
- Some tests are ignored due to being currently broken (see MakeFile). Make sure you update the list of ignored tests if it changes.
- tests in `test_create_command.py` are ignored as they modify `conf_client.yml`, which can interfere with your local setup. if you make changes that could affect these commands then your PR will fail the test workflow.

## Fix Test Discovery

Create a symlink to work around conda environment detection:
```bash
mkdir -p ~/anaconda3/envs/hummingbot/envs
ln -s ~/anaconda3/envs/hummingbot/ ~/anaconda3/envs/hummingbot/envs/hummingbot
```

This fixes a known conda issue ([#12082](https://github.com/conda/conda/issues/12082)) that prevents test discovery when conda is installed in a conda environment.
