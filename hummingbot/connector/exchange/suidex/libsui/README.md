# Setting up suibase and pysui

_for manual testing purposes_

1. Install suibase
2. run hummingbot env in local
   ```bash
   conda activate hummingbot
   ```
4. Setup localnet and get wallet information
   ```bash
    localnet start; localnet status
   # localnet stop //when stopping the localnet 
   # localnet regen // if you have previously started localnet before
   # ps aux | grep "[s]uibase" | awk '{print $2}' | xargs kill //if you want to stop the daemon completely   
   ```
5. Get active wallet info
   ```bash
   lsui keytool export --key-identity sb-1-ed25519
   ```
   and paste this into your local .env file that is imported in sui_client_config.py
6. Deploy Contract
   ```bash
   # in the dir of move.toml
    localnet publish --skip-dependency-verification
   ``` 
8. Add pysui to your project and make `devInspect` calls or `executeTransaction` calls

