"""``hbot gateway`` — detect, run, set up, and use the Gateway service (URL-first).

Gateway is a separate service (DEX/chain middleware) Hummingbot talks to at
``gateway_api_host:gateway_api_port`` (default localhost:15888). hbot is URL-first: if something
already serves Gateway there (a container OR a source run) it uses it; only otherwise does
``start`` launch the Docker image.

Files live in ``gateway-files/{conf,certs,logs}`` (the hummingbot-api convention), mounted into the
container at ``/home/gateway/{conf,certs,logs}``. Certs and wallet-key encryption both use the
keystore password (``GATEWAY_PASSPHRASE``), so a private key added via ``connect`` is stored
encrypted by Gateway under the same password as the rest of hbot.

First-run setup once Gateway is up:
    hbot gateway settings <namespace> <path> <value>   # set a namespace value (e.g. a chain's nodeURL)
    hbot gateway connect <chain>                        # add a wallet key (read from stdin, never argv)
    hbot gateway token-add <network> <address>          # track a token (e.g. solana-mainnet-beta <mint>)
    hbot gateway balance -n <network>                   # check on-chain wallet balances
"""
import asyncio
import getpass
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Tuple
from urllib.parse import urlencode

import typer

from hummingbot import prefix_path
from hummingbot.cli.output import ExitCode, SortedCommandsGroup, fail, print_json
from hummingbot.cli.password import resolve_password

if TYPE_CHECKING:
    from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient

CONTAINER = "hbot-gateway"
DEFAULT_IMAGE = "hummingbot/gateway:latest"
GATEWAY_FILES = "gateway-files"

gateway_app = typer.Typer(
    cls=SortedCommandsGroup, no_args_is_help=True,
    help="Run and use the Gateway service for on-chain (DEX) trading.")


def _client() -> Tuple[object, "GatewayHttpClient"]:
    from hummingbot.client.config.config_helpers import load_client_config_map_from_file
    from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
    client_config_map = load_client_config_map_from_file()
    return client_config_map, GatewayHttpClient(client_config_map.gateway)


def _gateway_dirs() -> Tuple[Path, Path, Path]:
    base = Path(prefix_path()) / GATEWAY_FILES
    return base / "conf", base / "certs", base / "logs"


def _arun(gw: "GatewayHttpClient", coro_factory):
    """Run a gateway coroutine, re-initializing the HTTP session for this event loop.

    GatewayHttpClient caches its aiohttp session globally; a CLI process may open more than one
    short-lived loop (e.g. ping, then wait-for-healthy), so we force a fresh session each time.
    """
    from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient

    async def _wrapped():
        GatewayHttpClient._http_client(gw._gateway_config, re_init=True)
        try:
            return await coro_factory()
        finally:
            if GatewayHttpClient._shared_client is not None:
                await GatewayHttpClient._shared_client.close()
                GatewayHttpClient._shared_client = None
    return asyncio.run(_wrapped())


def _is_running(gw: "GatewayHttpClient") -> bool:
    try:
        return _arun(gw, lambda: gw.ping_gateway())
    except Exception:
        return False


def _docker(*args: str) -> subprocess.CompletedProcess:
    """Run a `docker` CLI command. If the docker binary is absent (e.g. hbot running inside a container
    without Docker access), return a non-zero result instead of raising FileNotFoundError."""
    try:
        return subprocess.run(["docker", *args], capture_output=True, text=True)
    except FileNotFoundError:
        return subprocess.CompletedProcess(
            args=["docker", *args], returncode=127, stdout="", stderr="docker: command not found")


def _require_docker(json_output: bool) -> None:
    """Fail cleanly if the Docker CLI/daemon isn't usable here. This is the expected case when hbot runs
    inside a container: rather than docker-in-docker, run Gateway as a separate/sibling service and point
    hbot at it via `hbot settings gateway.gateway_api_host <host>` — the other gateway commands
    (status/balance/connect/token-*) then use it over the network, no Docker needed."""
    if _docker("version").returncode != 0:
        fail("Docker isn't available here, so hbot can't manage the Gateway container. Run Gateway as a "
             "separate service and point hbot at it: `hbot settings gateway.gateway_api_host <host>` "
             "(and gateway_api_port). Then `hbot gateway status`/`balance`/... use it over the network.",
             ExitCode.ERROR, json_output=json_output)


def _container_status() -> Optional[str]:
    result = _docker("ps", "-a", "--filter", f"name=^{CONTAINER}$", "--format", "{{.Status}}")
    return result.stdout.strip() or None


def _image_exists_locally(image: str) -> bool:
    return _docker("image", "inspect", image).returncode == 0


def _pull_image(image: str, json_output: bool, required: bool) -> bool:
    """``docker pull`` the image. Returns True if pulled. When ``required`` is False, a pull failure for
    an image that already exists locally is tolerated (e.g. a locally-built image not on a registry)."""
    result = _docker("pull", image)
    if result.returncode == 0:
        return True
    if required or not _image_exists_locally(image):
        fail(f"docker pull {image} failed: {result.stderr.strip()}", ExitCode.ERROR, json_output=json_output)
    return False


def _require_running(gw: "GatewayHttpClient", json_output: bool) -> None:
    if not _is_running(gw):
        fail("Gateway is not running — run `hbot gateway start` first",
             ExitCode.NOT_RUNNING, json_output=json_output)


def _read_secret(label: str, from_stdin: bool, json_output: bool) -> str:
    """Read a secret (private key) without it ever touching argv: stdin pipe or hidden prompt."""
    if from_stdin or not sys.stdin.isatty():
        value = sys.stdin.readline().rstrip("\n")
        if not value:
            fail("no value received on stdin", ExitCode.CONFIG_ERROR, json_output=json_output)
        return value
    return getpass.getpass(f"{label}: ")


def _split_network(network: str, json_output: bool) -> Tuple[str, str]:
    """Split a combined network id ('solana-mainnet-beta') into (chain, network) = ('solana', 'mainnet-beta').

    Gateway's chain-scoped endpoints (balances, token list/remove) want chain and network separately,
    while find/save take the combined form. We accept the combined form everywhere and split here.
    """
    chain, sep, net = network.partition("-")
    if not sep:
        fail(f"network must be in '<chain>-<network>' form, e.g. 'solana-mainnet-beta' (got '{network}')",
             ExitCode.CONFIG_ERROR, json_output=json_output)
    return chain, net


def _login_if_ssl(client_config_map, json_output: bool, password_stdin: bool = False) -> None:
    """In certs mode the client speaks https+mTLS, and its client key is encrypted with the keystore
    password — so we must log in before any Gateway call. No-op when SSL is disabled (HTTP mode)."""
    from hummingbot.client.config.config_crypt import ETHKeyFileSecretManger
    from hummingbot.client.config.security import Security
    if not client_config_map.gateway.gateway_use_ssl:
        return
    if Security.secrets_manager is not None:  # already logged in this process
        return
    password = resolve_password(password_stdin=password_stdin, json_output=json_output)
    if not Security.login(ETHKeyFileSecretManger(password)):
        fail("invalid password", ExitCode.CONFIG_ERROR, json_output=json_output)


@gateway_app.command("status")
def status(json_output: bool = typer.Option(False, "--json")) -> None:
    """Show whether Gateway is running."""
    client_config_map, gw = _client()
    _login_if_ssl(client_config_map, json_output)
    running = _is_running(gw)
    container = _container_status()
    if json_output:
        print_json({"ok": True, "running": running, "url": gw.base_url,
                    "managed_container": container is not None, "container_status": container})
        return
    typer.echo(f"Gateway: {'running' if running else 'not running'} at {gw.base_url}")
    if container is not None:
        typer.echo(f"hbot-gateway container: {container}")
    elif running:
        typer.echo("(running externally — e.g. from source)")


@gateway_app.command("pull")
def pull(
    image: str = typer.Option(DEFAULT_IMAGE, "--image", help="Gateway Docker image to pull."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Download the latest Gateway version."""
    _require_docker(json_output)
    _pull_image(image, json_output, required=True)
    if json_output:
        print_json({"ok": True, "image": image, "pulled": True})
    else:
        typer.echo(f"Pulled latest {image}.")


@gateway_app.command("start")
def start(
    image: str = typer.Option(DEFAULT_IMAGE, "--image", help="Gateway Docker image to run."),
    pull_latest: bool = typer.Option(
        True, "--pull/--no-pull", help="Pull the latest image before launching (default: pull)."),
    password_stdin: bool = typer.Option(
        False, "--password-stdin", help="Read the keystore/gateway passphrase from stdin."),
    timeout: float = typer.Option(90.0, "--timeout", help="Seconds to wait for Gateway to become healthy."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Start the Gateway service.

    Launches the Gateway in secure (HTTPS/mTLS) mode and waits until it's healthy; reuses one that is
    already running."""
    from hummingbot.client.config.config_crypt import ETHKeyFileSecretManger
    from hummingbot.client.config.config_helpers import save_to_yml
    from hummingbot.client.config.security import Security
    from hummingbot.client.settings import CLIENT_CONFIG_PATH
    from hummingbot.core.gateway import get_gateway_paths
    from hummingbot.core.utils.ssl_cert import create_self_sign_certs
    client_config_map, gw = _client()

    # Fast path: a gateway already answering on the current transport (no password needed for HTTP).
    if _is_running(gw):
        if json_output:
            print_json({"ok": True, "running": True, "url": gw.base_url, "started": False, "note": "already running"})
        else:
            typer.echo(f"Gateway already running at {gw.base_url} — using it.")
        return

    _require_docker(json_output)

    # The passphrase encrypts the certs AND the wallet keys Gateway stores; it must be the keystore password.
    passphrase = resolve_password(password_stdin=password_stdin, json_output=json_output)
    # Certs mode: the client speaks https+mTLS and its client key is encrypted with this passphrase, so
    # log in now (the post-launch health check and later commands need it).
    if not Security.login(ETHKeyFileSecretManger(passphrase)):
        fail("invalid password", ExitCode.CONFIG_ERROR, json_output=json_output)

    # Client and container must share ONE cert bundle for mTLS to validate. The client always reads its
    # certs from get_gateway_paths().local_certs_path (root_path()/certs), so generate there and mount
    # that into the container. conf/logs stay project-local under gateway-files.
    certs_dir = get_gateway_paths(client_config_map).local_certs_path
    conf_dir, _, logs_dir = _gateway_dirs()
    for d in (conf_dir, certs_dir, logs_dir):
        d.mkdir(parents=True, exist_ok=True)
    # Regenerate under the current passphrase so the client key is always decryptable with it.
    create_self_sign_certs(passphrase, certs_dir.as_posix())

    # Switch the client to https and persist it, then point this process's client at the secured URL.
    port = client_config_map.gateway.gateway_api_port
    if not client_config_map.gateway.gateway_use_ssl:
        client_config_map.gateway.gateway_use_ssl = True
        save_to_yml(CLIENT_CONFIG_PATH, client_config_map)
    gw.base_url = f"https://{client_config_map.gateway.gateway_api_host}:{port}"

    # Now that mTLS is possible, re-check: a secured gateway may already be up (e.g. from a prior start).
    if _is_running(gw):
        if json_output:
            print_json({"ok": True, "running": True, "url": gw.base_url, "started": False, "note": "already running"})
        else:
            typer.echo(f"Gateway already running at {gw.base_url} — using it.")
        return

    if pull_latest:
        _pull_image(image, json_output, required=False)

    _docker("rm", "-f", CONTAINER)  # clear any stale same-named container
    run = _docker(
        "run", "-d", "--name", CONTAINER,
        # Gateway exits its process on a config-triggered restart; let Docker bring it back.
        "--restart", "unless-stopped",
        "-p", f"{port}:{port}",
        "-v", f"{conf_dir.as_posix()}:/home/gateway/conf",
        "-v", f"{certs_dir.as_posix()}:/home/gateway/certs",
        "-v", f"{logs_dir.as_posix()}:/home/gateway/logs",
        "-e", f"GATEWAY_PASSPHRASE={passphrase}",
        # The image defaults to DEV=true (unsafe HTTP). Force secured HTTPS/mTLS (certs mode).
        "-e", "DEV=false",
        image,
    )
    if run.returncode != 0:
        fail(f"docker run failed: {run.stderr.strip()}", ExitCode.ERROR, json_output=json_output)

    async def _wait_healthy():
        deadline = time.time() + timeout
        while time.time() < deadline:
            if await gw.ping_gateway():
                return True
            await asyncio.sleep(2.0)
        return False

    if _arun(gw, _wait_healthy):
        if json_output:
            print_json({"ok": True, "running": True, "url": gw.base_url, "started": True, "image": image})
        else:
            typer.echo(f"Started Gateway ({image}) at {gw.base_url}.")
    else:
        fail(f"Gateway container started but did not become healthy within {timeout:g}s "
             f"(check `hbot gateway logs`)", ExitCode.TIMEOUT, json_output=json_output)


@gateway_app.command("stop")
def stop(json_output: bool = typer.Option(False, "--json")) -> None:
    """Stop the Gateway service."""
    container = _container_status()
    if container is None:
        _, gw = _client()
        if _is_running(gw):
            fail("Gateway is running but not managed by hbot (started externally/from source) — "
                 "stop it where you started it", ExitCode.ERROR, json_output=json_output)
        fail("no hbot-managed Gateway container", ExitCode.NOT_RUNNING, json_output=json_output)
    _docker("rm", "-f", CONTAINER)
    if json_output:
        print_json({"ok": True, "stopped": True})
    else:
        typer.echo("Stopped hbot-gateway container.")


@gateway_app.command("logs")
def logs(
    lines: int = typer.Option(200, "--lines", "-n", help="Number of trailing log lines."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Show the Gateway service's recent logs."""
    if _container_status() is None:
        fail("no hbot-managed Gateway container (logs are only available for containers hbot started)",
             ExitCode.NOT_RUNNING, json_output=json_output)
    result = _docker("logs", "--tail", str(lines), CONTAINER)
    typer.echo(result.stdout + result.stderr)


@gateway_app.command("settings")
def settings(
    namespace: Optional[str] = typer.Argument(
        None, help="Settings namespace (run with no args to list them, e.g. 'solana-mainnet-beta')."),
    path: Optional[str] = typer.Argument(None, help="Dotted settings path within the namespace (e.g. 'nodeURL')."),
    value: Optional[str] = typer.Argument(None, help="New value. Omit path+value to read the namespace's settings."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """View or change Gateway settings, grouped by namespace.

    Namespaces come from Gateway's /config/namespaces — chains/networks like 'solana-mainnet-beta' or
    'ethereum-mainnet', connectors like 'meteora', plus 'server'."""
    client_config_map, gw = _client()
    _login_if_ssl(client_config_map, json_output)
    _require_running(gw, json_output)

    if namespace is None:
        result = _arun(gw, lambda: gw.get_namespaces())
        names = result.get("namespaces", result) if isinstance(result, dict) else result
        if json_output:
            print_json({"ok": True, "namespaces": names})
        else:
            for n in names:
                typer.echo(n)
        return

    if path is None or value is None:
        cfg = _arun(gw, lambda: gw.get_configuration(namespace))
        if json_output:
            print_json({"ok": True, "namespace": namespace, "config": cfg})
        else:
            typer.echo(cfg)
        return

    try:
        _arun(gw, lambda: gw.update_config(namespace, path, value))
    except Exception as e:
        fail(f"settings update failed: {e}", ExitCode.ERROR, json_output=json_output)
    if json_output:
        print_json({"ok": True, "namespace": namespace, "path": path, "value": value})
    else:
        typer.echo(f"{namespace}.{path} = {value}  (Gateway restarting to apply)")


@gateway_app.command("connect")
def connect(
    chain: str = typer.Argument(..., help="Chain to add a wallet for (ethereum or solana)."),
    key_stdin: bool = typer.Option(False, "--key-stdin", help="Read the private key from stdin."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Add a wallet to a chain.

    The private key is read from stdin or a hidden prompt (never argv); Gateway stores it encrypted
    under the keystore passphrase."""
    client_config_map, gw = _client()
    _login_if_ssl(client_config_map, json_output)
    _require_running(gw, json_output)

    private_key = _read_secret(f"{chain} private key", key_stdin, json_output)
    try:
        result = _arun(gw, lambda: gw.add_wallet(chain, private_key=private_key))
    except Exception as e:
        fail(f"failed to add wallet: {e}", ExitCode.ERROR, json_output=json_output)

    address = result.get("address") if isinstance(result, dict) else None
    if json_output:
        print_json({"ok": True, "chain": chain, "address": address})
    else:
        typer.echo(f"Connected {chain} wallet{f': {address}' if address else ''} (key stored encrypted by Gateway).")


@gateway_app.command("disconnect")
def disconnect(
    chain: str = typer.Argument(..., help="Chain (ethereum or solana)."),
    address: str = typer.Argument(..., help="Wallet address to remove."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Remove a wallet from a chain."""
    client_config_map, gw = _client()
    _login_if_ssl(client_config_map, json_output)
    _require_running(gw, json_output)
    try:
        _arun(gw, lambda: gw.remove_wallet(chain, address))
    except Exception as e:
        fail(f"failed to remove wallet: {e}", ExitCode.ERROR, json_output=json_output)
    if json_output:
        print_json({"ok": True, "chain": chain, "address": address, "removed": True})
    else:
        typer.echo(f"Removed {chain} wallet {address}.")


@gateway_app.command("balance")
def balance(
    network: str = typer.Option(..., "--network", "-n", help="Chain-network, e.g. 'solana-mainnet-beta'."),
    tokens: Optional[List[str]] = typer.Argument(
        None, help="Token symbols/addresses to check. Omit to return all non-zero balances (incl. native)."),
    address: Optional[str] = typer.Option(
        None, "--address", "-a", help="Wallet address. Defaults to the chain's default wallet."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Show your on-chain wallet balances.

    With no tokens given, returns the native token plus all non-zero balances for tokens in the
    network's token list (use `hbot gateway token-add` to track more)."""
    client_config_map, gw = _client()
    _login_if_ssl(client_config_map, json_output)
    _require_running(gw, json_output)
    chain, net = _split_network(network, json_output)

    if address is None:
        address = _arun(gw, lambda: gw.get_default_wallet_for_chain(chain))
        if not address:
            fail(f"no wallet for {chain} — connect one with `hbot gateway connect {chain}` or pass --address",
                 ExitCode.NOT_FOUND, json_output=json_output)

    try:
        result = _arun(gw, lambda: gw.get_balances(chain, net, address, list(tokens or [])))
    except Exception as e:
        fail(f"failed to fetch balances: {e}", ExitCode.ERROR, json_output=json_output)

    balances = result.get("balances", result) if isinstance(result, dict) else {}
    if json_output:
        print_json({"ok": True, "network": network, "address": address, "balances": balances})
        return
    typer.echo(f"{chain} {net}  {address}")
    if not balances:
        typer.echo("(no balances)")
    for symbol, amount in balances.items():
        typer.echo(f"  {symbol}: {amount}")


# Token management is kept flat (`gateway token-list`, not `gateway token list`): the CLI is at most
# two levels deep so commands stay tab-discoverable and don't hide behind a third sub-app.
@gateway_app.command("token-list")
def token_list(
    network: str = typer.Argument(..., help="Chain-network, e.g. 'solana-mainnet-beta'."),
    search: Optional[str] = typer.Option(None, "--search", "-s", help="Filter by symbol or name."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List a network's tracked tokens."""
    client_config_map, gw = _client()
    _login_if_ssl(client_config_map, json_output)
    _require_running(gw, json_output)
    chain, net = _split_network(network, json_output)
    try:
        result = _arun(gw, lambda: gw.get_tokens(chain, net, search))
    except Exception as e:
        fail(f"failed to list tokens: {e}", ExitCode.ERROR, json_output=json_output)
    items = result.get("tokens", []) if isinstance(result, dict) else (result or [])
    if json_output:
        print_json({"ok": True, "network": network, "count": len(items), "tokens": items})
        return
    for t in items:
        typer.echo(f"  {t.get('symbol'):<12} {t.get('address')}")
    typer.echo(f"{len(items)} token(s)")


@gateway_app.command("token-find")
def token_find(
    network: str = typer.Argument(..., help="Chain-network, e.g. 'solana-mainnet-beta'."),
    address: str = typer.Argument(..., help="Token contract address to look up."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Look up a token by address, without saving it."""
    client_config_map, gw = _client()
    _login_if_ssl(client_config_map, json_output)
    _require_running(gw, json_output)
    _split_network(network, json_output)  # validate form
    try:
        token = _arun(gw, lambda: gw.api_request("get", f"tokens/find/{address}", params={"chainNetwork": network}))
    except Exception as e:
        fail(f"token not found: {e}", ExitCode.NOT_FOUND, json_output=json_output)
    if json_output:
        print_json({"ok": True, "network": network, "token": token})
        return
    typer.echo(token)


@gateway_app.command("token-add")
def token_add(
    network: str = typer.Argument(..., help="Chain-network, e.g. 'solana-mainnet-beta'."),
    address: str = typer.Argument(..., help="Token contract address to add."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Add a token to a network by its address.

    Metadata (symbol, name, decimals) is fetched automatically, so the network + address is all you
    need."""
    client_config_map, gw = _client()
    _login_if_ssl(client_config_map, json_output)
    _require_running(gw, json_output)
    _split_network(network, json_output)  # validate form
    # Gateway's save is POST with chainNetwork in the query; api_request would send params as a body,
    # so embed the query in the path (the address path segment carries the token to look up + persist).
    query = urlencode({"chainNetwork": network})
    try:
        result = _arun(gw, lambda: gw.api_request("post", f"tokens/save/{address}?{query}"))
    except Exception as e:
        fail(f"failed to add token: {e}", ExitCode.ERROR, json_output=json_output)
    if json_output:
        print_json({"ok": True, "network": network, "address": address, "result": result})
        return
    msg = result.get("message") if isinstance(result, dict) else None
    typer.echo(msg or f"Added token {address} to {network}.")


@gateway_app.command("token-remove")
def token_remove(
    network: str = typer.Argument(..., help="Chain-network, e.g. 'solana-mainnet-beta'."),
    address: str = typer.Argument(..., help="Token contract address to remove."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Remove a token from a network by its address."""
    client_config_map, gw = _client()
    _login_if_ssl(client_config_map, json_output)
    _require_running(gw, json_output)
    chain, net = _split_network(network, json_output)
    # Gateway reads chain/network from the query string for DELETE; api_request would send them as a body,
    # so embed them in the path instead.
    query = urlencode({"chain": chain, "network": net})
    try:
        result = _arun(gw, lambda: gw.api_request("delete", f"tokens/{address}?{query}"))
    except Exception as e:
        fail(f"failed to remove token: {e}", ExitCode.ERROR, json_output=json_output)
    if json_output:
        print_json({"ok": True, "network": network, "address": address, "removed": True, "result": result})
        return
    msg = result.get("message") if isinstance(result, dict) else None
    typer.echo(msg or f"Removed token {address} from {network}.")
