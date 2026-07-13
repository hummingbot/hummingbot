ARG BASE_IMAGE=hummingbot/hummingbot@sha256:0911b7cfa2612d7293341dc87f2661c906dd18a454a723b0ba8e69f69b3a4d7a
FROM ${BASE_IMAGE}

ARG RELEASE_ID=unknown
ARG SOURCE_SHA256=unknown
LABEL org.opencontainers.image.title="Hummingbot Strategy Evolution Loop" \
      org.opencontainers.image.revision="${RELEASE_ID}" \
      io.hummingbot.strategy-evolution.source-sha256="${SOURCE_SHA256}"

WORKDIR /home/hummingbot

COPY hummingbot/strategy_v2/backtesting/ hummingbot/strategy_v2/backtesting/
COPY hummingbot/strategy_v2/evolution/ hummingbot/strategy_v2/evolution/
COPY hummingbot/strategy_v2/executors/ hummingbot/strategy_v2/executors/
COPY controllers/ controllers/
COPY scripts/check_strategy_evolution_health.py scripts/
COPY scripts/run_pmm_mister_paper.sh scripts/
COPY scripts/strategy_evolution_backup.py scripts/
COPY scripts/strategy_evolution_loop.py scripts/
COPY scripts/v2_with_controllers.py scripts/
COPY scripts/walk_forward_funding_arb.py scripts/
COPY scripts/walk_forward_pmm_mister.py scripts/
COPY scripts/walk_forward_supertrend.py scripts/
COPY test/controllers/generic/test_pmm_mister.py test/controllers/generic/
COPY test/hummingbot/strategy_v2/test_funding_arbitrage_validation.py test/hummingbot/strategy_v2/
COPY test/hummingbot/strategy_v2/test_walk_forward.py test/hummingbot/strategy_v2/
COPY test/scripts/test_v2_funding_rate_arb.py test/scripts/
COPY test/hummingbot/strategy_v2/evolution/ test/hummingbot/strategy_v2/evolution/
COPY conf/strategy_evolution.json conf/strategy_evolution.json
COPY conf/controllers/conf_pmm_mister_paper.yml conf/controllers/conf_pmm_mister_paper.yml
COPY conf/scripts/conf_pmm_mister_paper.yml conf/scripts/conf_pmm_mister_paper.yml
COPY deploy/evolution/run.sh /usr/local/bin/strategy-evolution

RUN chmod 0555 /usr/local/bin/strategy-evolution scripts/run_pmm_mister_paper.sh

ENTRYPOINT ["/usr/local/bin/strategy-evolution"]
