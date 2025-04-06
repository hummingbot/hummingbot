import pluggy

hookspec = pluggy.HookspecMarker("diff_cover")


@hookspec
def diff_cover_report_quality():
    """
    Return a 2-part tuple:
    - Quality plugin name
    - Object that implements the BaseViolationReporter protocol
    """
