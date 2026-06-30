# `hbot` CLI install eval — source vs Docker (for agent-driven setup)

Goal: find the easiest path for an agent (Claude) to stand up the `hbot` CLI for a user.
Tested hands-on in a Claude Code remote sandbox (bare Python 3.11, no conda, outbound HTTPS via a
TLS-intercepting agent proxy). Date: 2026-06-30. Branch: `feat/hbot-cli` (merged into
`claude/hbot-cli-integration-jajfiq`).

## TL;DR

- **For a normal user machine, Docker is decisively the easier path** — *if the branch image is
  published*. `make deploy && make link-cli` is a registry pull + container start: no Miniconda, no
  `conda env create`, no Cython compile, pinned Python, prebuilt `.so`s. This is the path the skill
  and README now recommend for agents.
- **In this sandbox, only the source install actually completed.** Docker was blocked by two
  environment facts (image not yet pushed; build can't verify TLS through the proxy). Details below.
- **Action items for the maintainer** (see bottom) — chiefly: publish the image, and make the build
  proxy-CA aware.

## What was tested

### 1. Source install — ✅ completed, but heavy

Steps that were actually required (the repo's `make install` assumes conda already exists and that
`conda develop` works; neither held here, so several manual steps were needed):

1. Download + install Miniconda (**156 MB** installer) — no conda was present.
2. `conda tos accept …` for `pkgs/main` and `pkgs/r` — `conda env create` fails on the Anaconda
   channel Terms of Service until accepted.
3. `conda env create -f setup/environment.yml` — **~10 min**, resulting env is **3.2 GB**.
4. `conda develop .` **failed** — the base conda has no `conda-build` plugin, so the subcommand
   doesn't exist. Worked around by writing a `.pth` file into the env's site-packages (what
   `conda develop` does anyway).
5. `pip install -r setup/pip_packages.txt` — **`eip712-structs` failed to build** (only used by the
   `vertex` connector; non-fatal for the CLI, skipped).
6. Symlink `bin/hbot` into the env's `bin/`.
7. `python setup.py build_ext --inplace` — compile **61 Cython extensions** (~8 MB of `.so`, a few
   minutes).

Result: `hbot --version`, `--help`, `connectors`, `strategy list` work with no compile;
connector-touching commands (`ticker`, `balance`, …) work **only after** the Cython build.
(`hbot ticker binance BTC-USDT` returned HTTP 451 — a Binance geo-block in this region, not an
install problem.)

Friction worth noting:
- **Python drifted to 3.13.** `environment.yml` pins `python>=3.10.12`, so conda picked 3.13;
  upstream Hummingbot targets 3.10. Everything installed, but this is untested territory.
- `conda develop` reliance is fragile (see action items).
- End-to-end this is ~15 min of wall time, 3.2 GB on disk, and several non-obvious manual fixes — a
  lot for an agent to drive reliably.

### 2. Docker — ⚠️ could not complete in this sandbox

- The Docker **client** is present, but the **daemon was not running**; starting `dockerd` required
  root (available here, but not guaranteed in every sandbox).
- `docker-compose.yml` pulls `hummingbot/hummingbot:latest` — the **released** image, which does
  **not** contain the `hbot` CLI. The `feat/hbot-cli` image **is not published yet**, so `make
  deploy` cannot get a CLI-capable image.
- Building the image locally from the branch `Dockerfile` (tagged `hummingbot/hummingbot:latest` so
  `make deploy` would find it) **failed at `conda env create`**: inside the build container conda
  cannot verify TLS to `repo.anaconda.com` —
  `SSLError(CERTIFICATE_VERIFY_FAILED: self-signed certificate in chain)`. The agent proxy
  re-terminates TLS with a private CA (`/root/.ccr/ca-bundle.crt`); the host trusts it, but a
  `docker build` container does not inherit that trust, and the Dockerfile doesn't install a CA
  bundle or set `conda ssl_verify` / `REQUESTS_CA_BUNDLE`.

So the Docker *runtime* path (`deploy` → `hbot` via the `bin/hbot-host` wrapper, which `docker exec`s
into the container) is correct by inspection but could not be exercised here without a published
image. On a normal machine with Docker Desktop and direct internet, none of the above blockers exist.

## Verdict

| Dimension | Source | Docker (image published) |
|---|---|---|
| User-side steps | conda + ToS + env create + compile + path fixes | `make deploy && make link-cli` |
| Wall time (cold) | ~15 min | minutes (registry pull) |
| Disk | ~3.2 GB env + build | one image layer set |
| Cython compile on user machine | yes (61 ext) | no (prebuilt) |
| Python version control | drifts (got 3.13) | pinned in image |
| Failure surface for an agent | high (many manual steps) | low |
| Works in this TLS-proxy sandbox | **yes** | build blocked; runtime untested (no image) |

**For helping a typical user: recommend Docker.** It collapses the entire conda + compile dance into
a pull, which is exactly the agent-friendly path. Source remains the right choice only when building
or modifying the code — or, as in this sandbox, when Docker isn't usable.

The skill (`.agents/skills/hummingbot-cli/SKILL.md`) and `hummingbot/cli/README.md` were updated to
lead with Docker for agents and keep source as the build/modify path.

## Action items for the maintainer

1. **Publish the `feat/hbot-cli` image** to Docker Hub (`hummingbot/hummingbot:<tag>`). Until then
   `make deploy` pulls a CLI-less image and the recommended path doesn't work. This is the single
   biggest unblock.
2. **Make the Docker build proxy/CA aware** so it builds behind a TLS-intercepting proxy: accept an
   optional `--build-arg` CA bundle, copy it in, and set `conda config --set ssl_verify <path>` +
   `REQUESTS_CA_BUNDLE`/`PIP_CERT`. Helps CI and agent sandboxes alike.
3. **Drop the `conda develop` dependency in `install` / `make install`.** It needs the `conda-build`
   plugin in *base* conda, which a fresh Miniconda lacks, so it silently fails. Prefer `pip install
   -e .` or writing a `.pth` into the env.
4. **Pin Python explicitly** in `setup/environment.yml` (e.g. `python=3.10`) — `>=3.10.12` let conda
   resolve to 3.13, which upstream doesn't target.
5. **Fix or document the `eip712-structs` pip build failure** (`setup/pip_packages.txt`); it breaks
   `make install`'s pip step even though only the `vertex` connector needs it.
6. Optionally accept the Anaconda channel **ToS** automatically in `install`, or switch
   `environment.yml` to `conda-forge`-only channels to avoid the `defaults` ToS gate.
