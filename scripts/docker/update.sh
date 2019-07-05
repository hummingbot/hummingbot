# 1) Delete instance and old hummingbot image
docker rm hummingbot-instance && \
docker image rm coinalpha/hummingbot:latest

# 2) Re-create instance with latest hummingbot release
docker run -it \
--name hummingbot-instance \
--mount "type=bind,source=$(pwd)/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_logs,destination=/logs/" \
coinalpha/hummingbot:latest