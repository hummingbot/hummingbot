#!/bin/sh
cd ~
ROOT=$(pwd)
cd -
BASEDIR=$(dirname "$0")

export CONDAPATH=$ROOT"/miniconda3"
export PYTHON=${CONDAPATH}"/envs/hummingbot/bin/python3"

cd $BASEDIR
${PYTHON} bin/hummingbot.py
cd -
