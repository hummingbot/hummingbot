#!/usr/bin/python

if "kairos-dist" in __file__:
    # Dist environment.
    import os
    import sys
    sys.path.append(sys.path.pop(0))
    sys.path.insert(0, os.getcwd())

    import kairos
    kairos.set_prefix_path(os.getcwd())
else:
    # Dev environment.
    import sys
    from os.path import join, realpath
    sys.path.insert(0, realpath(join(__file__, "../../")))
