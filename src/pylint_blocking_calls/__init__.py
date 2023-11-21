from pylint.lint import PyLinter

from .checker import BlockingCallsChecker


def register(linter: PyLinter) -> None:
    """Register the checker as the PyLint plugin"""
    linter.register_checker(BlockingCallsChecker(linter))
