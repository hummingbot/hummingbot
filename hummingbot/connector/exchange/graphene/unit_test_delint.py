r"""
black_all.py

WTFPL litepresence.com Jan 2021

A simple script that blacks, isorts, and pylints *.py files
"""

# STANDARD PYTHON MODULES
import os
from time import time

# these can be safely ignored in most circumstances
DISABLE = (
    # too many?
    "too-many-statements",
    "too-many-locals",
    "too-many-branches",
    "too-many-function-args",
    "too-many-arguments",
    "too-many-nested-blocks",
    "too-many-lines",
    # improper exception handling
    "bare-except",
    "broad-except",
    # snake_case, etc.
    "invalid-name",
    # sometimes it just can't find the modules referenced - on this machine
    "import-error",
    # whitespace authoritarianism
    "bad-continuation",
    "bad-whitespace",
    # class minimums
    "too-few-public-methods",
    "no-self-use",
    # suppression
    "suppressed-message",
    "locally-disabled",
    "useless-suppression",
)


def auto_enumerate(name):
    """
    swap enumerate() in place of range(len())
    """
    with open(name, "r") as handle:
        data = handle.read()
        handle.close()

    data = data.split("\n")
    total = 0
    final_data = []
    for line in data:
        if ", _  in enumerate(" in line and "):" in line:
            line = line.replace(" in range(len(", ", _  in enumerate(").replace(
                ")):", "):"
            )
            total += 1
        final_data.append(line)
    final_data = "\n".join(final_data).strip("\n") + "\n"

    with open(name, "w") as handle:
        handle.write(final_data)
        handle.close()
    if total:
        print(f"{total} range(len()) instances enumerated in {name}!")


def auto_broad_except(name):
    """
    convert 'except:' to 'except Exception:'
    """
    with open(name, "r") as handle:
        data = handle.read()
        handle.close()

    data = data.split("\n")
    total = 0
    final_data = []
    for line in data:
        if "except:" in line:
            line = line.replace("except:", "except Exception:")
            total += 1
        final_data.append(line)
    final_data = "\n".join(final_data).strip("\n") + "\n"

    with open(name, "w") as handle:
        handle.write(final_data)
        handle.close()
    if total:
        print(f"{total} bare excepts replaced in {name}")


def auto_double_line_break(name):
    """
    Remove extra line breaks
    """

    with open(name, "r") as handle:
        data = handle.read()
        handle.close()
    total = 0
    for _ in range(3):
        data_split = data.split("\n\n\n")
        data = "\n\n".join(data_split)
        total += len(data_split) - 1
    with open(name, "w") as handle:
        handle.write(data)
        handle.close()
    if total:
        print(f"{total} double line brakes replaced in {name}")


def main():
    """
    \033c\nWelcome to lite Black Pylint Lite All! \n
    """
    print(main.__doc__)
    dispatch = {
        1: "Black Pylint Lite All!",
        2: "Black Pylint All!",
        3: "Pylint Lite All Only",
        4: "Pylint All Only",
        5: "Black All Only",
    }
    print("          Menu\n")
    for key, val in dispatch.items():
        print("         ", key, "  :  ", val)
    choice = input("\n\nInput Number or Press Enter for Choice 1\n\n  ")
    if choice == "":
        choice = 1
    choice = int(choice)
    disabled = ""
    if choice in [1, 3]:
        disabled = "--enable=all --disable="
        for item in DISABLE:
            disabled += item + ","
        disabled.rstrip(",")
    # Get the start time
    start = time()
    # Clear the screen
    print("\033c")
    # Get all of the python files in the current folder
    pythons = [f for f in os.listdir() if f.endswith(".py") and f != "black_all.py"]
    # pythons = [f for f in os.listdir() if f in ONLY]

    pythons = [f for f in pythons if "test" not in f]

    for name in pythons:
        auto_double_line_break(name)
    # For every file in that list:
    if choice in [1, 2, 5]:
        for name in pythons:
            # Print the script we are blacking.
            print("Blacking script:", name)
            # Black the script.
            os.system(f"black -l 88 --experimental-string-processing {name}")
            # Print a divider.
            print("-" * 100)
    print("Isorting all scripts")
    os.system("isort *.py")
    for name in pythons:
        auto_enumerate(name)
    for name in pythons:
        auto_broad_except(name)
    if choice in [1, 2, 3, 4]:
        for name in pythons:
            # Print the script we are blacking.
            print("Pylinting script:", name)
            # Black the script.
            os.system(f"pylint {name} {disabled}")
            # Print a divider.
            print("-" * 100)
    # Say we are done.
    print("Done.")
    # Get the end time:
    end = time()
    # Find the time it took to black the scripts.
    took = end - start
    # Print that time.
    print(len(pythons), "scripts took %.1f" % took, "seconds.")


if __name__ == "__main__":
    main()
