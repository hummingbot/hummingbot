# 1) Update package database
sudo apt update
# 2) Install dependencies
sudo apt install -y apt-transport-https ca-certificates curl gnupg2 software-properties-common tmux
# 3) Register Docker repository to your system
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo apt-key add -
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/debian $(lsb_release -cs) stable"
sudo apt update
# 4) Install Docker
sudo apt install -y docker-ce
# 5) Change permissions for docker (optional)
# Allow docker commands without requiring sudo prefix
sudo usermod -a -G docker $USER
# 6) Close terminal window
exit