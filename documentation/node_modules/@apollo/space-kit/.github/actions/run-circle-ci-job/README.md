# Run Check Label

This action will take the current branch and re-run the `check-label` CI task.

This uses the new JavaScript GitHub actions API. One weird step is that we don't actually install `node_modules`, so we need to either commit `node_modules` to source control or we need to bundle everything. We are using the GitHub recommended method of bundling the code. Use the `npm` script `build:github-checks` before pushing. 
