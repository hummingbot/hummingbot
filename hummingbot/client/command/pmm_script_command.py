from typing import List


class PMMScriptCommand:

    def pmm_script_command(self, cmd: str = None, args: List[str] = None):
        if self._pmm_script_iterator is not None:
            self._pmm_script_iterator.request_command(cmd, args)
        else:
            self.notify('No PMM script is active, command ignored')

        return True
