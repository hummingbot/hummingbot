# IDEX Connector


All commands should be executed from the `hummingbot` conda environment. To start the hummingbot env run:
`conda activate hummingbot`.

## Local Setup

https://docs.hummingbot.io/operation/client/#start-hummingbot-from-source

```
# 1) Clean intermediate and compiled files from Cython compilation.
./clean

# 2) Install
./install

# 3) Deactivate old conda environment
conda deactivate

# 4) Activate conda environment
conda activate hummingbot

# 5) Compile
./compile

# 6) Run Hummingbot
bin/hummingbot.py
```


## Tests

`nosetests -v ./test/integration/test_idex_*`
