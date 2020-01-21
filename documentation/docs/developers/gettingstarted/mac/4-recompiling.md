# Developer Quickstart – macOS | Re-compiling

This section walks you through re-compiling Hummingbot after a code change.

```bash tab="Re-Compiling Hummingbot"
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

---
# Next: [Using the Debug Console](/developers/debug)
