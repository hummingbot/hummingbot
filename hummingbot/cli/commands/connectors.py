"""``hbot connectors`` — list the available connectors, grouped by spot and perpetual.

The catalog of exchanges you *can* connect to (static — no keystore, no network). To see which you've
already connected, use ``hbot connect``.
"""
from hummingbot.cli.output import echo


def connectors() -> None:
    """List the available connectors, grouped by spot and perpetual."""
    from hummingbot.client.settings import AllConnectorSettings, ConnectorType
    settings = AllConnectorSettings.get_connector_settings()
    spot, perp, other = [], [], []
    for name, cs in settings.items():
        if cs.type in (ConnectorType.Exchange, ConnectorType.CLOB_SPOT):
            spot.append(name)
        elif cs.type in (ConnectorType.Derivative, ConnectorType.CLOB_PERP):
            perp.append(name)
        else:
            other.append(name)

    sections = [(f"spot ({len(spot)})", spot), (f"perpetual ({len(perp)})", perp)]
    if other:
        sections.append((f"other ({len(other)})", other))
    echo("\n\n".join(f"## {title}\n\n{', '.join(sorted(names))}" for title, names in sections))
