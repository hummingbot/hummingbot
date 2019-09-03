# SETUP FILE PATHS
export CONDAPATH="$(pwd)/miniconda3"
export PYTHON="$(pwd)/miniconda3/envs/hummingbot/bin/python3"
export hummingbotPath="$(pwd)/hummingbot" && cd $hummingbotPath
# REMOVE OLD INSTALLATION
${CONDAPATH}/bin/deactivate
./uninstall
rm -rf $(pwd)/miniconda3/envs/hummingbot
./clean
# UPDATE HUMMINGBOT
# 1) Download latest code
git pull origin master
# 5) Install Hummingbot
./install
# 6) Activate environment and compile code
${CONDAPATH}/bin/activate hummingbot && ${PYTHON} setup.py build_ext --inplace
# 7) Start Hummingbot
${PYTHON} bin/hummingbot.py