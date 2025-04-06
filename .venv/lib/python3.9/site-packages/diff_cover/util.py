import os.path
import posixpath


def to_unix_path(path):
    """
    Tries to ensure tha the path is a normalized unix path.
    This seems to be the solution cobertura used....
    https://github.com/cobertura/cobertura/blob/642a46eb17e14f51272c6962e64e56e0960918af/cobertura/src/main/java/net/sourceforge/cobertura/instrument/ClassPattern.java#L84

    I know of at least one case where this will fail (\\) is allowed in unix paths.
    But I am taking the bet that this is not common. We deal with source code.

    :param path: string of the path to convert
    :return: the unix version of that path
    """
    return posixpath.normpath(os.path.normcase(path).replace("\\", "/"))
