# -*- coding: utf-8 -*-

from typing import Dict


class BeaxyStompMessage:
    def __init__(self, command: str = "") -> None:
        self.command = command
        self.body: str = ""
        self.headers: Dict[str, str] = {}

    def serialize(self) -> str:
        result = self.command + '\n'
        result += ''.join([f'{k}:{self.headers[k]}\n' for k in self.headers])
        result += '\n'
        result += self.body
        result += '\0'
        return result

    def has_error(self) -> bool:
        return self.headers.get('status') != '200'

    @staticmethod
    def deserialize(raw_message: str) -> 'BeaxyStompMessage':
        lines = raw_message.splitlines()
        retval = BeaxyStompMessage()
        for index, line in enumerate(lines):
            if index == 0:
                retval.command = line
            else:
                split = line.split(':')
                if len(split) == 2:
                    retval.headers[split[0].strip()] = split[1].strip()
                else:
                    if line:
                        line_index = raw_message.index(line)
                        retval.body = raw_message[line_index:]
                        retval.body = "".join(c for c in retval.body if c not in ['\r', '\n', '\0'])
                        break

        return retval
