import re


def get_pygeth_version() -> str:
    with open("setup.py") as f:
        setup_contents = f.read()
    version_match = re.search(r"py-geth\s*([><=~!]+)\s*([\d.]+)", setup_contents)
    if version_match:
        return "".join(version_match.group(1, 2))
    else:
        raise ValueError("py-geth not found in setup.py")


if __name__ == "__main__":
    version = get_pygeth_version()
    print(version)
