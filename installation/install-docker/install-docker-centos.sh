# 1) Update package database
sudo yum check-update
# 2) Install Docker
curl -fsSL https://get.docker.com/ | sh 
# 3) Start and Automate Docker
sudo systemctl start docker && sudo systemctl enable docker 
# 4) Change permissions for docker (optional)
# Allow docker commands without requiring sudo prefix
sudo usermod -a -G docker $USER
# 5) Close terminal window
exit