import os
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Set, Tuple

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.interfaces import IAstroidChecker
from pylint.lint import PyLinter

from . import helpers


class BlockingCallsChecker(BaseChecker):
    __implements__ = IAstroidChecker
    name = "blocking-calls"
    msgs = {
        "W0002": (
            "%s",
            "blocking-call",
            "There is a call that may block an async function.",
        )
    }
    options = (
        (
            "blocking-function-names",
            {
                "default": os.getenv("BLOCKING_FUNCTION_NAMES") or "",
                "type": "regexp_csv",
                "metavar": "<comma-separated-names>",
                "help": "Comma-separated regexps for names of the synchronous functions that may block the event loop.",
            },
        ),
        (
            "skip-functions",
            {
                "default": os.getenv("SKIP_FUNCTIONS") or "",
                "type": "regexp_csv",
                "metavar": "<comma-separated-names>",
                "help": "Comma-separated regexps for names of the functions in which we shouldn't look for the blocking calls.",
            },
        ),
        (
            "skip-modules",
            {
                "default": os.getenv("SKIP_MODULES") or "",
                "type": "regexp_csv",
                "metavar": "<comma-separated-names>",
                "help": "Comma-separated regexps for module names in which we shouldn't look for blocking calls.",
            },
        ),
        (
            "skip-decorated",
            {
                "default": os.getenv("SKIP_DECORATED") or "",
                "type": "regexp_csv",
                "metavar": "<comma-separated-names>",
                "help": "Comma-separated regexps for decorator names. If a function is decorated with one of these decorators, we won't look for blocking calls inside it.",
            },
        ),
    )

    def __init__(self, linter: Optional[PyLinter] = None) -> None:
        super().__init__(linter)

        # caches for inner purpose
        self._all_visited_calls: Dict[str, List[nodes.Call]] = defaultdict(list)
        self._calls_of_blocking_functions: List[nodes.Call] = []
        self._blocking_calls_hashes: Set[str] = set()

    def visit_call(self, call: nodes.Call) -> None:
        """Called each time when a `nodes.Call` node is visited"""
        if self._should_call_be_checked(call):
            call_name = helpers.get_call_name(call)
            if call_name is not None:
                # cache each visited call by the call name
                self._all_visited_calls[call_name].append(call)
                if self._is_blocking_function_call(call_name):
                    # collect calls of the blocking functions
                    self._calls_of_blocking_functions.append(call)

    def _should_call_be_checked(self, call: nodes.Call) -> bool:
        """Whether the call should be checked or not."""
        frame = call.frame()
        if not isinstance(frame, (nodes.FunctionDef, nodes.AsyncFunctionDef)):
            # skip calls that happens outside a function (they can't be blocking)
            return False
        for regexp in self.config.skip_modules:
            if regexp.match(self.linter.current_name):
                # skip calls that happen inside a module that should be skipped
                return False
        for regexp in self.config.skip_functions:
            if regexp.match(frame.name):
                # skip calls that happen inside a function that should be skipped
                return False
        return True

    def _is_blocking_function_call(self, call_name: str) -> bool:
        """Check if it is the call of a blocking function."""
        for regexp in self.config.blocking_function_names:
            if regexp.match(call_name):
                return True
        return False

    def close(self):
        """This method is called once after checking all .py files."""
        self._traverse_blocking_function_calls(self._calls_of_blocking_functions)

    def _traverse_blocking_function_calls(
        self,
        calls_to_traverse: List[nodes.Call],
        traversed_sequence: Tuple[nodes.Call, ...] = (),
    ) -> None:
        """Traverse the blocking functions calls with the recursive DFS.

        Find all the blocking calls, and add messages for them.
        """
        for call in calls_to_traverse:
            if self._should_stop_traversal(call, traversed_sequence):
                continue
            function_def: helpers.FunctionDef = call.frame()
            # if the call happens inside an async function, it's a blocking call
            if isinstance(function_def, nodes.AsyncFunctionDef):
                if helpers.get_call_node_hash(call) not in self._blocking_calls_hashes:
                    # hash the call node to avoid messages duplicates
                    self._add_blocking_call_message(call, reversed(traversed_sequence))
                    self._blocking_calls_hashes.add(helpers.get_call_node_hash(call))
                # stop traversal for this path when found a blocking call
                continue
            self._traverse_blocking_function_calls(
                self._get_calls_of_function(function_def), traversed_sequence + (call,)
            )

    def _should_stop_traversal(
        self, call: nodes.Call, traversed_sequence: Tuple[nodes.Call, ...]
    ) -> bool:
        if call in traversed_sequence:
            # stop traversal if we found a loop
            return True
        function_def: helpers.FunctionDef = call.frame()
        for regexp in self.config.skip_decorated:
            for name in helpers.get_function_decorator_names(function_def):
                if regexp.match(name):
                    # skip when reached a function decorated with a decorator that should be skipped
                    return True
        return False

    def _add_blocking_call_message(
        self, blocking_call: nodes.Call, calls_sequence: Iterable[nodes.Call]
    ) -> None:
        self.add_message(
            "blocking-call",
            node=blocking_call,
            args=(
                self._call_sequence_to_str((blocking_call,) + tuple(calls_sequence)),
            ),
        )

    @staticmethod
    def _call_sequence_to_str(calls_sequence: Tuple[nodes.Call, ...]) -> str:
        return " -> ".join(helpers.get_call_name(call) for call in calls_sequence)

    def _get_calls_of_function(
        self, function_def: helpers.FunctionDef
    ) -> List[nodes.Call]:
        """Get all the found calls of the given function."""
        possible_call_name = helpers.get_function_name(function_def)
        return self._all_visited_calls.get(possible_call_name) or []


def register(linter: PyLinter) -> None:
    linter.register_checker(BlockingCallsChecker(linter))
