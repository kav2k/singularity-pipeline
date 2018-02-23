from __future__ import print_function

import sys
import colorama


class EPrint():
    def __init__(self, print_func=None, debug=False):
        if not print_func:
            print_func = self.__eprint
        self.print_func = print_func
        self.debug = debug

    def __eprint(self, *args, **kwargs):
        """Default print function: print to sys.stderr.

        Follows same format as print()."""
        print(*args, file=sys.stderr, **kwargs)

    def normal(self, *args, **kwargs):
        """Print text normally.

        Follows same format as print()."""
        self.print_func(*args, **kwargs)

    def bold(self, *args, **kwargs):
        """Print text as bold.

        Follows same format as print()."""
        args = list(args)
        if len(args):
            args[0] = colorama.Style.BRIGHT + args[0]
            args[-1] = args[-1] + colorama.Style.RESET_ALL
        self.print_func(*args, **kwargs)

    def red(self, *args, **kwargs):
        """Print text as bold red.

        Follows same format as print()."""
        args = list(args)
        if len(args):
            args[0] = colorama.Fore.RED + colorama.Style.BRIGHT + args[0]
            args[-1] = args[-1] + colorama.Style.RESET_ALL
        self.print_func(*args, **kwargs)

    def yellow(self, *args, **kwargs):
        """Print text as bold yellow.

        Follows same format as print()."""
        args = list(args)
        if len(args):
            args[0] = colorama.Fore.YELLOW + colorama.Style.BRIGHT + args[0]
            args[-1] = args[-1] + colorama.Style.RESET_ALL
        self.print_func(*args, **kwargs)

    def debug(self, *args, **kwargs):
        """Print text as bold cyan if debug flag is set,
        does nothing otherwise.

        Follows same format as print()."""
        if self.debug:
            args = list(args)
            if len(args):
                args[0] = colorama.Fore.CYAN + colorama.Style.BRIGHT + args[0]
                args[-1] = args[-1] + colorama.Style.RESET_ALL
            self.print_func(*args, **kwargs)
