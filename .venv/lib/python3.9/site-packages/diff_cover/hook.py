import pluggy

# Other packages that implement diff_cover plugins use this.
hookimpl = pluggy.HookimplMarker("diff_cover")
