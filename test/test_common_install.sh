#!/bin/bash

# Include the functions from your main script here
source "$(dirname "$0")/../common_install.sh"

# Test that find_github_conda returns a conda executable
test__find_conda() {
  # Set up the test environment
  local test_dir=$(mktemp -d)

  local conda_dir="${test_dir}/conda_dir"
  mkdir -p "${conda_dir}"
  touch "${conda_dir}/conda"
  chmod +x "${conda_dir}/conda"

  # Run the function and check the result
  local result=$(_find_conda_in_dir "${test_dir}")
  if [[ "$result" == "" ]]; then
      echo "test_find_github_conda 'activate' not found: passed"
  else
      echo "test_find_github_conda passed"
      echo "   Expected: "
      echo "        Got: ${result}"
  fi

  # With activate exists, not necessarily executable
  touch "${conda_dir}/activate"

  local result=$(_find_conda_in_dir "${test_dir}")
  if [[ "$result" == "${conda_dir}/conda" ]]; then
      echo "test_find_github_conda with 'activate': passed"
  else
      echo "test_find_github_conda passed"
      echo "   Expected: ${conda_dir}/conda"
      echo "        Got: ${result}"
  fi

  # Not exec
  chmod -x "${conda_dir}/conda"

  local result=$(_find_conda_in_dir "${test_dir}")
  if [[ "$result" == "" ]]; then
      echo "test_find_github_conda not exec: passed"
  else
      echo "test_find_github_conda passed"
      echo "   Expected: "
      echo "        Got: ${result}"
  fi

  # Max depth 5
  rm -rf "${test_dir}"/conda*
  mkdir -p "${test_dir}/conda_dir/conda_dir/conda_dir/conda_dir/conda_dir/conda_dir"
  local conda_dir="${test_dir}/conda_dir/conda_dir/conda_dir/conda_dir/conda_dir/conda_dir"

  touch "${conda_dir}/conda"
  chmod +x "${conda_dir}/conda"
  touch "${conda_dir}/activate"

  # Run the function and check the result
  local result=$(_find_conda_in_dir "${test_dir}")
  if [[ "$result" == "" ]]; then
      echo "test_find_github_conda maxdepth 5: passed"
  else
      echo "test_find_github_conda failed"
      echo "   Expected: "
      echo "        Got: ${result}"
  fi

  # Clean up the test environment
  rm -rf "${test_dir}"
}

# Tests for _find_conda_in_paths
test__find_conda_in_paths() {
  # Set up the test environment
  local test_dir1=$(mktemp -d)
  local test_dir2=$(mktemp -d)
  local test_dir3=$(mktemp -d)

  mkdir -p "${test_dir1}"/conda_dir "${test_dir2}"/conda_dir "${test_dir3}"/conda_dir
  touch "${test_dir1}"/conda_dir/{conda,activate} "${test_dir2}"/conda_dir/{conda,activate} "${test_dir3}"/conda_dir/{conda,activate}
  # Third dir does not have an executable 'conda'
  chmod +x "${test_dir1}"/conda_dir/conda "${test_dir2}"/conda_dir/conda

  # Run the function and capture the output
  result=$(_find_conda_in_paths "${test_dir1}" "${test_dir2}") 2> /dev/null

  # Check the result
  if [[ "${result}" != "${test_dir1}/conda_dir/conda ${test_dir2}/conda_dir/conda" ]]; then
    echo "test_find_conda_in_paths failed"
    echo "  Expected: ${test_dir1}/conda_dir/conda ${test_dir2}/conda_dir/conda"
    echo "  Got: ${result}"
  else
    echo "test_find_conda_in_paths passed"
  fi

  # Clean up the test environment
  rm -rf "${test_dir1}" "${test_dir2}" "${test_dir3}"
}


# Test _find_latest_conda_version
test_find_latest_conda_version() {
  mock_conda() {
    local version=$1
    shift
    if [[ "$1" == "info" && "$2" == "--json" ]]; then
      echo "{\"conda_version\": \"${version}\"}"
    else
      echo "Unexpected command: $@" >&2
      exit 1
    fi
  }

  export -f mock_conda
  # Setup some mock conda directories and versions
  local test_dir1=$(mktemp -d)
  local test_dir2=$(mktemp -d)
  local test_dir3=$(mktemp -d)

  echo -e '#!/bin/bash\nmock_conda "1.2.3" "$@"' > "${test_dir1}"/conda
  echo -e '#!/bin/bash\nmock_conda "1.2.4" "$@"' > "${test_dir2}"/conda
  echo -e '#!/bin/bash\nmock_conda "1.2.5" "$@"' > "${test_dir3}"/conda

  chmod +x "${test_dir1}"/conda "${test_dir2}"/conda "${test_dir3}"/conda

  # Run the function and capture the output
  result=$(_find_latest_conda_version "${test_dir1}"/conda "${test_dir2}"/conda "${test_dir3}"/conda)

  # Check the result
  if [[ "${result}" != "${test_dir3}/conda" ]]; then
    echo "test_find_latest_conda_version failed"
    echo "  Expected: ${test_dir3}/conda"
    echo "  Got: ${result}"
  else
    echo "test_find_latest_conda_version passed"
  fi

  # Test 3 conda is not executable, it is skipped and Test 2 conda is used
  chmod -x "${test_dir3}"/conda
  # Run the function and capture the output
  result=$(_find_latest_conda_version "${test_dir1}"/conda "${test_dir2}"/conda "${test_dir3}"/conda)

  # Check the result
  if [[ "${result}" != "${test_dir2}/conda" ]]; then
    echo "test_find_latest_conda_version non-executable conda: failed"
    echo "  Expected: ${test_dir2}/conda"
    echo "  Got: ${result}"
  else
    echo "test_find_latest_conda_version non-executable conda: passed"
  fi

  # Test 2 no longer returns a valid version, Test 1 conda is used
  echo -e '#!/bin/bash\nmock_conda "" "$@"' > "${test_dir2}"/conda
  # Run the function and capture the output
  result=$(_find_latest_conda_version "${test_dir1}"/conda "${test_dir2}"/conda "${test_dir3}"/conda)

  # Check the result
  if [[ "${result}" != "${test_dir1}/conda" ]]; then
    echo "test_find_latest_conda_version empty version: failed"
    echo "  Expected: ${test_dir21}/conda"
    echo "  Got: ${result}"
  else
    echo "test_find_latest_conda_version empty version: passed"
  fi


  # Clean up the test environment
  rm -rf "${test_dir1}" "${test_dir2}" "${test_dir3}"
}

test_find_conda_exe_in_github() {
  MOCKED_GITHUB_DIR=$(mktemp -d)
  echo -e '#!/bin/bash\nmock_conda "1.2.3" "$@"' > "${MOCKED_GITHUB_DIR}"/conda
  touch "${MOCKED_GITHUB_DIR}"/activate

  _find_conda_in_dir() {
    local path=$1
    if [[ "${path}" == "/home/runner" ]]; then
      echo "${MOCKED_GITHUB_DIR}/conda"
    else
      echo "${path}/conda"
    fi
  }

  export MOCKED_GITHUB_DIR
  export -f _find_conda_in_dir

  mock_conda() {
    local version=$1
    shift
    if [[ "$1" == "info" && "$2" == "--json" ]]; then
      echo "{\"conda_version\": \"${version}\"}"
    else
      echo "Unexpected command: $@" >&2
      exit 1
    fi
  }

  export -f mock_conda

  # Setup some mock conda directories and versions
  local test_dir1=$(mktemp -d)
  local test_dir2=$(mktemp -d)
  local test_dir3=$(mktemp -d)

  # Create conda and activate files
  echo -e '#!/bin/bash\nmock_conda "1.2.3" "$@"' > "${test_dir1}"/conda
  echo -e '#!/bin/bash\nmock_conda "1.2.4" "$@"' > "${test_dir2}"/conda
  echo -e '#!/bin/bash\nmock_conda "1.2.5" "$@"' > "${test_dir3}"/conda
  touch "${test_dir1}"/activate
  touch "${test_dir2}"/activate
  touch "${test_dir3}"/activate

  chmod +x "${test_dir1}"/conda "${test_dir2}"/conda "${test_dir3}"/conda

  # Run the function and capture the output
  local _CONDA_PATH="$CONDA_PATH"
  local _CONDA_EXE="$CONDA_EXE"
  unset CONDA_PATH
  unset CONDA_EXE
  conda_exe=$(find_conda_exe)
  export CONDA_PATH="$_CONDA_PATH"
  export CONDA_EXE="$_CONDA_EXE"

  # Check the result - This should output the "/home/runner/conda" file
  if [[ "${conda_exe}" != "${MOCKED_GITHUB_DIR}/conda" ]]; then
    echo "test_find_conda_exe failed"
    echo "  Expected: ${MOCKED_GITHUB_DIR}/conda"
    echo "  Got: ${conda_exe}"
  else
    echo "test_find_conda_exe passed"
  fi

  # Clean up the test environment
  rm -rf "${test_dir1}" "${test_dir2}" "${test_dir3}"
  unset -f _find_conda_in_dir
}

test_find_conda_exe() {
  _find_conda_in_paths() {
    if [ $# -ge 5 ]  # ~/.conda /opt/conda/bin /usr/share /usr/local /root/*conda*/bin + paths
    then
      paths=()
      for ((i=5; i<${#}; i++)); do
        paths+="${@:i+1:1}/conda"
      done
      echo "${test_dir1}/conda ${test_dir2}/conda ${test_dir3}/conda ${paths[@]}"
    else
      echo "Unexpected input: $@" >&2
      exit 1
    fi
  }

  export -f _find_conda_in_paths

  mock_conda() {
    local version=$1
    shift
    if [[ "$1" == "info" && "$2" == "--json" ]]; then
      echo "{\"conda_version\": \"${version}\"}"
    else
      echo "Unexpected command: $@" >&2
      exit 1
    fi
  }

  export -f mock_conda

  # Setup some mock conda directories and versions
  local test_dir1=$(mktemp -d)
  local test_dir2=$(mktemp -d)
  local test_dir3=$(mktemp -d)

  export test_dir1 test_dir2 test_dir3

  # Create conda and activate files
  echo -e '#!/bin/bash\nmock_conda "1.2.3" "$@"' > "${test_dir1}"/conda
  echo -e '#!/bin/bash\nmock_conda "1.2.4" "$@"' > "${test_dir2}"/conda
  echo -e '#!/bin/bash\nmock_conda "1.2.5" "$@"' > "${test_dir3}"/conda
  touch "${test_dir1}"/activate
  touch "${test_dir2}"/activate
  touch "${test_dir3}"/activate

  chmod +x "${test_dir1}"/conda "${test_dir2}"/conda "${test_dir3}"/conda

  # Run the function and capture the output
  local _CONDA_PATH="$CONDA_PATH"
  local _CONDA_EXE="$CONDA_EXE"
  unset CONDA_PATH
  unset CONDA_EXE
  conda_exe=$(find_conda_exe)
  export CONDA_PATH="$_CONDA_PATH"
  export CONDA_EXE="$_CONDA_EXE"

  # Check the result
  if [[ "${conda_exe}" != "${test_dir3}/conda" ]]; then
    echo "test_find_conda_exe failed"
    echo "  Expected: ${test_dir3}/conda"
    echo "  Got: ${conda_exe}"
  else
    echo "test_find_conda_exe with several conda paths: passed"
  fi

  # Run the function and capture the output
  local conda_path_dir=$(mktemp -d)

  export conda_path_dir

  # Create conda and activate files
  echo -e '#!/bin/bash\nmock_conda "1.2.6" "$@"' > "${conda_path_dir}"/conda
  chmod +x "${conda_path_dir}"/conda
  touch "${conda_path_dir}"/activate

  local _CONDA_PATH="$CONDA_PATH"
  local _CONDA_EXE="$CONDA_EXE"
  unset CONDA_EXE
  CONDA_PATH="${conda_path_dir}"
  conda_path=$(find_conda_exe)
  export CONDA_PATH="$_CONDA_PATH"
  export CONDA_EXE="$_CONDA_EXE"

  # Check the result
  if [[ "${conda_path}" != "${conda_path_dir}/conda" ]]; then
    echo "test_find_conda_exe failed"
    echo "  Expected: ${conda_path_dir}/conda"
    echo "  Got: ${conda_path}"
  else
    echo "test_find_conda_exe with higher conda CONDA_PATH: passed"
  fi

  local conda_exe_dir=$(mktemp -d)
  export conda_exe_dir
  echo -e '#!/bin/bash\nmock_conda "1.2.7" "$@"' > "${conda_exe_dir}"/conda
  chmod +x "${conda_exe_dir}"/conda
  touch "${conda_exe_dir}"/activate

  local _CONDA_PATH="$CONDA_PATH"
  local _CONDA_EXE="$CONDA_EXE"
  CONDA_EXE="${conda_exe_dir}/conda"
  conda_exe=$(find_conda_exe)
  export CONDA_PATH="$_CONDA_PATH"
  export CONDA_EXE="$_CONDA_EXE"

  # Check the result
  if [[ "${conda_exe}" != "${conda_exe_dir}/conda" ]]; then
    echo "test_find_conda_exe failed"
    echo "  Expected: ${conda_exe_dir}/conda"
    echo "  Got: ${conda_exe}"
  else
    echo "test_find_conda_exe with higher conda CONDA_EXE: passed"
  fi

  # Clean up the test environment
  rm -rf "${test_dir1}" "${test_dir2}" "${test_dir3}" "${conda_exe_dir}" "${conda_path_dir}"
  unset -f _find_conda_in_paths
}

test__verify_path() {
  # Testing absolute path
  local abs_path="/usr/bin"
  local result=$(_verify_path "${abs_path}")
  if [[ "${result}" != "${abs_path}" ]]; then
    echo "test__verify_path failed: absolute path test"
    echo "  Expected: ${abs_path}"
    echo "  Got: ${result}"
    exit 1
  fi

  # Testing relative path
  local rel_path="test_directory"
  local expected_result="$(pwd)/${rel_path}"
  local result=$(_verify_path "${rel_path}")
  if [[ "${result}" != "${expected_result}" ]]; then
    echo "test__verify_path failed: relative path test"
    echo "  Expected: ${expected_result}"
    echo "  Got: ${result}"
    exit 1
  fi

  echo "test__verify_path passed"
}

element_in_array() {
  local element="$1"
  shift
  local array=("$@")
  for el in "${array[@]}"; do
    if [[ "$el" == "$element" ]]; then
      return 0  # return success (in shell 0 is success, non-zero is failure)
    fi
  done
  return 1  # return failure
}

test__list_files_on_pattern() {
  local initial_dir=$(pwd)
  local test_dir=$(mktemp -d)
  touch "${test_dir}"/file1.txt
  touch "${test_dir}"/file2.txt
  touch "${test_dir}"/file3.txt
  mkdir "${test_dir}"/subdir
  touch "${test_dir}"/subdir/file4.txt
  local expected_files=("file1.txt" "file2.txt" "file3.txt")

  cd "${test_dir}" || exit

  local files=($(_list_files_on_pattern "." ".txt" | sort))
  if ! element_in_array "file1.txt" "${files[@]}" ||
     ! element_in_array "file2.txt" "${files[@]}" ||
     ! element_in_array "file3.txt" "${files[@]}"; then
    echo "test__list_files_on_pattern failed"
    echo "  Expected: ${expected_files[@]}"
    echo "  Got: ${files[@]}"
    exit 1
  fi
  cd "${initial_dir}" || exit

  # Providing path to directory
  local files=($(_list_files_on_pattern "${test_dir}" ".txt"))
  if ! element_in_array "file1.txt" "${files[@]}" ||
     ! element_in_array "file2.txt" "${files[@]}" ||
     ! element_in_array "file3.txt" "${files[@]}"; then
    echo "test__list_files_on_pattern failed"
    echo "  Expected files are missing in the output"
    exit 1
  fi

  rm -rf "${test_dir}"
  echo "test__list_files_on_pattern passed"
}

test__select_index_from_list() {
  local options=("Option1" "Option2" "Option3")
  local prompt="Select an option"
  local timeout=10

  # Mock function for read
  # replace the actual read with our mock function
  local real_read=$(which read)
  read() {
    if [ "$1" = "-r" -a \
         "$2" = "-t" -a \
         "$3" = "${timeout}" -a \
         "$4" = "-p" -a \
         "$5" = "${prompt} [1-${#options[@]}] (1): " -a \
         "$6" = "user_input" \
    ]; then
      local -n __result=$6
      __result=2
    else
      echo "Unexpected arguments to read: $*" >&2
      exit 1
    fi
  }

  export -f read

  local selection=$(_select_index_from_list options "${prompt}" $timeout)
  if [[ "${selection}" != "1" ]]; then
    echo "test__select_index_from_list failed"
    echo "  Expected: 1"
    echo "  Got: ${selection}"
    exit 1
  fi

  echo "test__select_index_from_list passed"

  # remove our mock function
  unset -f read
}

test_get_env_file() {
  # Setup some mock environment files
  local test_dir=$(mktemp -d)
  touch "${test_dir}"/env1.yml
  touch "${test_dir}"/env2.yml
  touch "${test_dir}"/env2._yml

  # Run the function and capture the output
  result=$(get_env_file "${test_dir}/env1.yml" "Selection" 1)

  # Check the result
  if ! element_in_array "env1.yml" "${result[@]}"; then
    echo "test_get_env_file failed"
    echo "  Expected: env1.yml"
    echo "  Got: ${result}"
  else
    echo "test_get_env_file passed"
  fi

  # Clean up the test environment
  rm -rf "${test_dir}"
}

test_get_env_name() {
  # Setup a mock environment file
  local test_dir=$(mktemp -d)
  echo 'name: test_env' > "${test_dir}"/env.yml

  # Run the function and capture the output
  result=$(get_env_name "${test_dir}/env.yml")

  # Check the result
  if [[ "${result}" != "test_env" ]]; then
    echo "test_get_env_name failed"
    echo "  Expected: test_env"
    echo "  Got: ${result}"
  else
    echo "test_get_env_name passed"
  fi

  # Clean up the test environment
  rm -rf "${test_dir}"
}

test__update_package_version() {
  local package="$1"
  local version="$2"
  local upper_version="$3"
  local old_version="$4"
  local expected="$5"

  # Create a temporary file
  temp_file=$(mktemp)

  # Add the package to the file without any version constraint
  echo "$package" > "$temp_file"

  # Update the version using the function
  _update_package_version "$temp_file" "$package" "$version" "$upper_version" "$old_version"

  # Check that the output is as expected
  output=$(cat "$temp_file")
  if [[ "$output" == "$expected" ]]; then
    echo "Test passed!"
  else
    echo "Test failed. Expected '$expected' but got '$output'"
  fi

  # Clean up
  rm "$temp_file"
}

# Run tests
# test__find_conda
# test__find_conda_in_paths
# test_find_latest_conda_version
# test_find_conda_exe_in_github
# test_find_conda_exe
# test__verify_path
# test__list_files_on_pattern
# test__select_index_from_list
# test_get_env_file
# test_get_env_name
test__update_package_version "urllib3" "1.26.6" "2.0" "" "urllib3>=1.26.6,<2.0"
test__update_package_version "urllib3" "1.26.6" "" "old_version" "urllib3>=1.26.6"
test__update_package_version "urllib3" "1.26.6" "" "" "urllib3>=1.26.6"

run_test_cases_common_install() {
  echo "Running test cases for common_install.sh..."

  test__find_conda 2> /dev/null >1 /dev/null
  if [ $? -ne 0 ]; then
    echo "FAIL: test__find_conda"
    exit 1
  fi

  test__find_conda_in_paths 2> /dev/null >1 /dev/null
  if [ $? -ne 0 ]; then
    echo "FAIL: test__find_conda_in_paths"
    exit 1
  fi

  test_find_latest_conda_version 2> /dev/null >1 /dev/null
  if [ $? -ne 0 ]; then
    echo "FAIL: test_find_latest_conda_version"
    exit 1
  fi

  test_find_conda_exe_in_github 2> /dev/null >1 /dev/null
  if [ $? -ne 0 ]; then
    echo "FAIL: test_find_conda_exe_in_github"
    exit 1
  fi

  test_find_conda_exe 2> /dev/null >1 /dev/null
  if [ $? -ne 0 ]; then
    echo "FAIL: test_find_conda_exe"
    exit 1
  fi

  test__verify_path 2> /dev/null >1 /dev/null
  if [ $? -ne 0 ]; then
    echo "FAIL: test__verify_path"
    exit 1
  fi

  test__list_files_on_pattern 2> /dev/null >1 /dev/null
  if [ $? -ne 0 ]; then
    echo "FAIL: test__list_files_on_pattern"
    exit 1
  fi

  test__select_index_from_list 2> /dev/null >1 /dev/null
  if [ $? -ne 0 ]; then
    echo "FAIL: test__select_index_from_list"
    exit 1
  fi

  test_get_env_file 2> /dev/null >1 /dev/null
  if [ $? -ne 0 ]; then
    echo "FAIL: test_get_env_file"
    exit 1
  fi

  test_get_env_name 2> /dev/null >1 /dev/null
  if [ $? -ne 0 ]; then
    echo "FAIL: test_get_env_name"
    exit 1
  fi

  echo "PASS: all test cases for hummingbot-start.sh"
}

run_test_cases_common_install
