# 1) Install dependencies
sudo yum install -y wget bzip2 git
sudo yum groupinstall -y 'Development Tools'
# 2) Install Miniconda3
wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
sh Miniconda3-latest-Linux-x86_64.sh
export CONDAPATH="$(pwd)/miniconda3" && \
export PYTHON="$(pwd)/miniconda3/envs/hummingbot/bin/python3" && \
# INSTALL HUMMINGBOT
# 4) Clone Hummingbot
git clone https://github.com/CoinAlpha/hummingbot.git && \
# 5) Install Hummingbot
export hummingbotPath="$(pwd)/hummingbot" && cd $hummingbotPath && ./install && \
# 6) Activate environment and compile code
${CONDAPATH}/bin/activate hummingbot && ${PYTHON} setup.py build_ext --inplace && \
# 7) Start Hummingbot
${PYTHON} bin/hummingbot.py