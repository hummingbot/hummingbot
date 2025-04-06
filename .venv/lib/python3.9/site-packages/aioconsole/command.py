"""Provide an asynchronous equivalent to the python console."""

import sys
import argparse
import shlex

from . import console


class AsynchronousCli(console.AsynchronousConsole):
    def __init__(
        self, commands, streams=None, *, prog=None, prompt_control=None, loop=None
    ):
        super().__init__(streams=streams, prompt_control=prompt_control, loop=loop)
        self.prog = prog
        self.commands = dict(commands)
        self.commands["help"] = (
            self.help_command,
            argparse.ArgumentParser(description="Display the help message."),
        )
        self.commands["list"] = (
            self.list_command,
            argparse.ArgumentParser(description="Display the command list."),
        )
        self.commands["exit"] = (
            self.exit_command,
            argparse.ArgumentParser(description="Exit the interface."),
        )
        for key, (corofunc, parser) in self.commands.items():
            parser.prog = key
            parser.print_help = lambda file=sys.stderr, *, self=parser: type(
                parser
            ).print_help(self, file)

    def get_default_banner(self):
        prog = self.prog or sys.argv[0].split("/")[-1]
        msg = f"Welcome to the CLI interface of {prog}!\n"
        msg += "Try:\n"
        msg += " * 'help' to display the help message\n"
        msg += " * 'list' to display the command list."
        return msg

    async def help_command(self, reader, writer):
        return """\
Type 'help' to display this message.
Type 'list' to display the command list.
Type '<command> -h' to display the help message of <command>."""

    async def list_command(self, reader, writer):
        msg = "List of commands:"
        for key, (corofunc, parser) in sorted(self.commands.items()):
            usage = parser.format_usage().replace("usage: ", "")[:-1]
            msg += "\n * " + usage
        return msg

    async def exit_command(self, reader, writer):
        raise SystemExit

    async def runsource(self, source, filename=None):
        # Parse the source
        if source.strip().endswith("\\"):
            return True
        source = source.replace("\\\n", "")
        try:
            name, *args = shlex.split(source)
        except ValueError:
            return False

        # Get the command
        if name not in self.commands:
            self.write(f"Command '{name}' does not exist.\n")
            await self.flush()
            return False
        corofunc, parser = self.commands[name]

        # Patch print_message so the parser prints to our console
        parser._print_message = lambda message, file=None: message and self.write(
            message
        )

        # Parse arguments
        try:
            namespace = parser.parse_args(args)
        except SystemExit:
            return False

        # Run the coroutine
        coro = corofunc(self.reader, self.writer, **vars(namespace))
        try:
            result = await coro
        except SystemExit:
            raise

        # Prompt the traceback or result
        except BaseException:
            self.showtraceback()
        else:
            if result is not None:
                self.write(str(result) + "\n")
        await self.flush()
        return False
