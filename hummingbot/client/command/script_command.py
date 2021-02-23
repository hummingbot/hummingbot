from typing import List


class ScriptCommand:

    def script_command(self, cmd: str = None, args: List[str] = None):
        if self._script_iterator is not None:
            self._script_iterator.request_command(cmd, args)
        else:
            self._notify('No script is active, command ignored')

        return True
