import argparse
import os
from posixpath import join, realpath
from typing import List

import yaml

parser: argparse.ArgumentParser = argparse.ArgumentParser(
    description="Generates the necessary configuration files from templates."
)

parser.add_argument("--host-conf-path",
                    type=str,
                    required=True,
                    help="Specify a path to which the gateway configs should be stored.")

parser.add_argument("--infura-api-key",
                    type=str,
                    required=False,
                    help="Specify the Infura API Key to use for the Infura node.")

args = parser.parse_args()

GATEWAY_TEMPLATE_PATH = realpath(join(__file__, "../../src/templates/"))
template_file_list: List[str] = os.listdir(GATEWAY_TEMPLATE_PATH)

for template in template_file_list:
    with open(f"{GATEWAY_TEMPLATE_PATH}/{template}") as file:
        yaml_config = yaml.full_load(file)
        
        for item, doc in yaml_config.items():
            print(f"{item}: {doc}")

print(GATEWAY_TEMPLATE_PATH)
print(template_file_list)
print(args)