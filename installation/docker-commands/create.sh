# 1) Create folder for your new instance
mkdir hummingbot_files
# 2) Create folders for log and config files
mkdir hummingbot_files/hummingbot_conf && mkdir hummingbot_files/hummingbot_logs
# Create a new instance of hummingbot
docker run -it \
--name hummingbot-instance \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_logs,destination=/logs/" \
coinalpha/hummingbot:latest