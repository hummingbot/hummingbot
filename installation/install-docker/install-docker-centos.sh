# 1) Update package database
sudo yum check-update
# 2) Install tmux
sudo yum -y install tmux
# 3) Install Docker
curl -fsSL https://get.docker.com/ | sh 
# 4) Start and Automate Docker
sudo systemctl start docker && sudo systemctl enable docker 
# 5) Change permissions for docker (optional)
# Allow docker commands without requiring sudo prefix
sudo usermod -a -G docker $USER
# 6) Close terminal window
exit