# SETUP DEPENDENCIES

# 1) Install dependencies
sudo apt-get update
sudo apt-get install -y build-essential git

# 2) Install Miniconda3
wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
sh Miniconda3-latest-Linux-x86_64.sh

# 3) Log out and log back into shell to register "conda" command
exit
# Log back into or open a new Linux terminal