# Create a new instance of hummingbot
docker run -it \
--name hummingbot-instance \
--mount "type=bind,source=$(pwd)/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_logs,destination=/logs/" \
coinalpha/hummingbot:latest