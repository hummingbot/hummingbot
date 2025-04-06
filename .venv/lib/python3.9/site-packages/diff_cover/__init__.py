try:
    from importlib.metadata import version
except ImportError:
    # Importlib.metadata introduced in python 3.8
    import pkg_resources

    def version(package):
        return pkg_resources.get_distribution(package).version


VERSION = version("diff_cover")
DESCRIPTION = "Automatically find diff lines that need test coverage."
QUALITY_DESCRIPTION = "Automatically find diff lines with quality violations."
