# 1) Update Ubuntu's database of software
sudo apt-get update
# 2) Install tmux
sudo apt-get install -y tmux
# 3) Install Docker
sudo apt install -y docker.io
# 4) Start and Automate Docker
sudo systemctl start docker && sudo systemctl enable docker 
# 5) Change permissions for docker (optional)
# Allow docker commands without requiring sudo prefix
sudo usermod -a -G docker $USER 
# 6) Close terminal window
exit