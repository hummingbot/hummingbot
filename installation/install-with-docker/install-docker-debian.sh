# INSTALL DOCKER
# 1) Update package database
sudo apt update
# 2) Install dependencies
sudo apt install -y apt-transport-https ca-certificates curl gnupg2 software-properties-common
# 3) Register Docker repository to your system
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo apt-key add -
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/debian $(lsb_release -cs) stable"
sudo apt update
# 4) Install Docker
sudo apt install -y docker-ce
# 5) Change permissions for docker (optional)
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