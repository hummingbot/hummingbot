# 1) Update package database
sudo yum check-update
# 2) Install Docker
curl -fsSL https://get.docker.com/ | sh 
# 3) Start and Automate Docker
sudo systemctl start docker && sudo systemctl enable docker 
# 4) Change permissions for docker (optional)
# Allow docker commands without requiring sudo prefix
sudo usermod -a -G docker $USER
# INSTALL HUMMINGBOT
# 1) Create folder for your new instance
mkdir hummingbot_files
# 2) Create folders for log and config files
mkdir hummingbot_files/hummingbot_conf && mkdir hummingbot_files/hummingbot_logs
# 3) Launch a new instance of hummingbot
sudo docker run -it \
--name hummingbot-instance \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_logs,destination=/logs/" \
coinalpha/hummingbot:latest