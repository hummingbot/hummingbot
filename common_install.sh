#!/bin/bash

# Compatibility logic for older Anaconda versions.
find_conda_exe() {
    local -n _conda_exe=$1
    if [ "${_conda_exe} " == " " ]; then
      _conda_exe=$(( \
        find /opt/conda/bin/conda || \
        find ~/anaconda3/bin/conda || \
        find /usr/local/anaconda3/bin/conda || \
        find ~/miniconda3/bin/conda  || \
        find /root/miniconda/bin/conda || \
        find ~/Anaconda3/Scripts/conda) 2>/dev/null \
      )
    fi

    if [ "${_conda_exe}_" == "_" ]; then
        echo "Please install Anaconda w/ Python 3.7+ first"
        echo "See: https://www.anaconda.com/distribution/"
        exit 1
    fi
}

get_env_file() {
    local env_file=$1
    local env_dir=$(dirname ${env_file})
    local env_ext="${env_file##*.}"

    local files=( $(find ${env_dir} -type f -name "*.${env_ext}") )
    local i=1
    for file in "${files[@]}"; do
        echo "   ${i}: ${file}" >&2
        i=$((i+1))
    done

    local user_input
    while true; do
        read -t 10 -p "Enter your choice [1-${#files[@]}]: " user_input
        if [ "${user_input}_" == "_" ]; then
            echo $env_file
            return
        fi
        if [[ ${user_input} -ge 1 && ${user_input} -le ${#files[@]} ]]; then
            break
        else
            echo "Invalid selection. Please enter a number between 1 and ${#files[@]}." >&2
        fi
    done

    echo ${files[$((user_input-1))]}
}

get_env_name() {
    local env_file=$1
    local valid_env_name=$(grep  'name:' ${env_file} | tail -n1 | awk '{ print $2}')
    local response
    read -t 10 -p "Enter environment name [${valid_env_name}](10s wait): " response
    if [ "${response}_" == "_" ]; then
        response=${valid_env_name}
    fi

    echo ${response}
}

check_env_name() {
  local conda_exe="$1"
  local env_file="$2"
  local conda_agent="$3"
  local valid_env_name
  valid_env_name=$(grep  'name:' "${env_file}" | tail -n1 | awk '{ print $2}')
  read -t 30 -p "Enter environment name [${valid_env_name}](30s wait): " response
  if [ "${response}_" == "_" ]; then
    echo ""
    echo "  -> Using default environment name: ${valid_env_name}"
    echo "                   environment file: ${env_file}"
    echo "                   Conda user_agent: ${conda_agent}"
    response=${valid_env_name}
  fi

  local env_name="${response}"

  if [ "$env_name" != "$valid_env_name" ]; then
    echo "*** Incompatible environment name in ${env_file} (${valid_env_name}). Please resolve and try again."
    exit 1
  fi
}

