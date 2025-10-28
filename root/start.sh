#!/usr/bin/with-contenv bash
# shellcheck shell=bash

echo "Starting Hummingbot. . ."
echo $LSIO_NON_ROOT_USER
if [[ -z ${LSIO_READ_ONLY_FS} ]] && [[ -z ${LSIO_NON_ROOT_USER} ]]; then
    sudo -u abc BASH_ENV=\${HOME}/.bashrc /bin/bash -c "conda activate hummingbot && /home/hummingbot/bin/hummingbot_quickstart.py 2>> /home/hummingbot/logs/errors.log"
else
    conda activate hummingbot && /home/hummingbot/bin/hummingbot_quickstart.py 2>> /home/hummingbot/logs/errors.log
fi
