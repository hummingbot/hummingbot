# 1) Update Ubuntu's database of software
sudo apt-get update
# 2) Install Docker
sudo apt install -y docker.io
# 3) Start and Automate Docker
sudo systemctl start docker && sudo systemctl enable docker 
# 4) Change permissions for docker (optional)
# Allow docker commands without requiring sudo prefix
sudo usermod -a -G docker $USER 
# 5) Close terminal window
exit