#!/usr/bin/env python3
r"""
patch_generated_proto_list.py

This script patches a generated Protobuf Python file to bypass duplicate descriptor
registration errors. It does so by reading a list of descriptor names (as a JSON array)
from a file (the "list file"). Then, for each occurrence of:

    DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(<serialized_bytes>)

the script checks if any descriptor name from the list is found in the serialized literal.
If a match is found, it replaces the registration call with a try/except block that first
attempts to find the descriptor by name via FindFileByName() and falls back to AddSerializedFile().

Usage:
    python patch_generated_proto_list.py --file path/to/generated_proto.py --list_file descriptors.json

For example, if descriptors.json contains:
    ["amino/amino.proto", "dydx_v4_ns_amino/dydx_v4_ns_amino.proto"]

and a generated file contains:
    DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x19amino/amino.proto\x12...')
the script will replace it with:

    try:
        DESCRIPTOR = _descriptor_pool.Default().FindFileByName("amino/amino.proto")
    except KeyError:
        DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x19amino/amino.proto\x12...')

This helps bypass duplicate registration errors.
"""

import argparse
import os
import re
import sys


def patch_file(file_path):
    """Patch the generated proto file using the descriptor list."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}", file=sys.stderr)
        sys.exit(1)

    # Regex to capture the call to AddSerializedFile:
    # It matches lines like:
    #   DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(<serialized_bytes>)
    pattern = re.compile(
        r'(DESCRIPTOR\s*=\s*_descriptor_pool\.Default\(\)\.AddSerializedFile\()'  # group 1: before literal
        r'(.*?)'  # group 2: the serialized literal (non-greedy)
        r'(\))',  # group 3: closing parenthesis
        re.DOTALL
    )

    def replacement(match, descriptor_key=None):
        original_literal = match.group(2).strip()
        if descriptor_key is None:
            return match.group(0)
        new_block = (
            'try:\n'
            '    DESCRIPTOR = _descriptor_pool.Default().FindFileByName("' + descriptor_key + '")\n'
            'except KeyError:\n'
            '    DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(' + original_literal + ')'
        )
        return new_block

    # Find the first descriptor from the list that appears in the content.
    # descriptor_key = next((d for d in descriptor_list if f"source: {d}" in content), None)
    descriptor_key_re = re.compile(r'# source: (.*\.proto)')
    search_key = descriptor_key_re.search(content)
    descriptor_key = search_key.group(1) if search_key else None

    already_applied = re.compile(r'(DESCRIPTOR\s*=\s*_descriptor_pool\.Default\(\)\.FindFileByName\()')

    if descriptor_key is None or already_applied.search(content):
        return

    new_content, count = pattern.subn(lambda m: replacement(m, descriptor_key), content)

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
    except Exception as e:
        print(f"Error writing file {file_path}: {e}", file=sys.stderr)
        sys.exit(1)
    # print(f"File '{file_path}' updated successfully.")


def main():
    parser = argparse.ArgumentParser(
        description="Patch generated Protobuf Python files using a list of descriptor names to bypass duplicate registration errors."
    )
    parser.add_argument("--file", required=True, help="Path to the generated .py file to patch")
    args = parser.parse_args()

    if not os.path.isfile(args.file):
        print(f"Error: File '{args.file}' does not exist.", file=sys.stderr)
        sys.exit(1)

    patch_file(args.file)


if __name__ == "__main__":
    main()
