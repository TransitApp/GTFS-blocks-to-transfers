"""
Handles the printing of warnings generated during processing.
"""

import textwrap
import sys


class Warn(Exception):
    N_INDENT = 4
    any_warnings = False

    def __init__(self, raw_message):
        Warn.any_warnings = True

        # Force standard formatting for message
        lines = raw_message.replace(Warn.N_INDENT * ' ',
                                    '').strip().splitlines()
        message = [f'Warning: {lines[0]}']
        message.extend(Warn.indent(line) for line in lines[1:])
        message.append('')

        super().__init__('\n'.join(message))

    @staticmethod
    def indent(text, level=1):
        return Warn.N_INDENT * level * ' ' + text

    def print(self):
        print(str(self), file=sys.stderr)
