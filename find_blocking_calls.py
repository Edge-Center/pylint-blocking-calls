import re
from collections import defaultdict
from typing import (
    Dict,
    Iterable,
    List,
    Optional,
    Set,
    Tuple,
)

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.interfaces import IAstroidChecker
from pylint.lint import PyLinter


class BlockingCallsChecker(BaseChecker):
    """Find all blocking calls in the codebase.

    Use # pylint: disable=blocking-call to skip a blocking call.
    """

    __implements__ = IAstroidChecker
    name = "blocking-calls"
    msgs = {
        "W0002": (
            "%s",
            "blocking-call",
            "Arises when there is a blocking call in an async function.",
        )
    }
    options = (
        (
            "blocking-function-names",
            {
                "default": r"^.*auth\.get_auth_ref$,^.*barbican.*\..+$,^.*cinder.*\..+$,^.*glance.*\..+$,^.*heat.*\..+$,^.*ironic.*\..+$,^.*neutron.*\..+$,^.*nova.*\..+$,^.*octavia.*\..+$,^get_session$,^.*session.*\.(commit|delete|rollback|refresh|close)$,^.*session.*\..+\.get$,^requests\.(get|post|put|patch|delete)$,^.+\.(one|one_or_none|all|first)$,^.*keystone.*\.(access_rules|application_credentials|auth|credentials|ec2|endpoint_filter|endpoint_groups|endpoint_policy|endpoints|domain_configs|domains|federation|groups|limits|policies|projects|registered_limits|regions|role_assignments|roles|inference_rules|services|simple_cert|tokens|trusts|users).*$",
                "type": "regexp_csv",
                "metavar": "<comma-separated-names>",
                "help": "Comma-separated names of methods that are blocking.",
            },
        ),
        (
            "skip-functions",
            {
                "default": r"^delete_.+$,",
                "type": "regexp_csv",
                "metavar": "<comma-separated-names>",
                "help": "Comma-separated regexps for functions in which we shouldn't check for blocking calls.",
            },
        ),
        (
            "skip-modules",
            {
                "default": r"^src\.db\.task$,^src\.db\.tasks\..+$,^src\.worker\..+$,^src\.tests\..+$",
                "type": "regexp_csv",
                "metavar": "<comma-separated-names>",
                "help": "Comma-separated regexps for module names in which we shouldn't check for blocking calls.",
            },
        ),
    )

    # pylint: disable=no-member
    def __init__(self, linter: Optional[PyLinter] = None) -> None:
        super().__init__(linter)

        self._blocking_function_names_like: List[re.Pattern] = self.config.blocking_function_names
        self._skip_functions: List[re.Pattern] = self.config.skip_functions
        self._skip_modules: List[re.Pattern] = self.config.skip_modules

        # caches for inner purpose
        self._all_visited_calls: Dict[str, List[nodes.Call]] = defaultdict(list)
        self._calls_of_blocking_functions: List[nodes.Call] = []
        self._blocking_calls_hashes: Set[str] = set()

    def visit_call(self, call: nodes.Call) -> None:
        """Called each time when a `nodes.Call` node is visited"""
        if self._should_call_be_checked(call):
            call_name = utils.get_call_name(call)
            if call_name is not None:
                # cache each visited call which happens inside a function
                self._all_visited_calls[call_name].append(call)
                if self._is_blocking_function_call(call):
                    # collect possible blocking calls
                    self._calls_of_blocking_functions.append(call)

    def _should_call_be_checked(self, call: nodes.Call) -> bool:
        """Whether the call should be checked or not."""
        frame = call.frame()
        if not isinstance(frame, (nodes.FunctionDef, nodes.AsyncFunctionDef)):
            # skip calls that happens outside of a function (they can't be blocking)
            return False
        for regexp in self._skip_modules:
            if regexp.match(self.linter.current_name):
                # skip calls that should be skipped by its module name
                return False
        for regexp in self._skip_functions:
            if regexp.match(frame.name):
                # skip calls that should be skipped by its function name
                return False
        return True

    def _is_blocking_function_call(self, call: nodes.Call) -> bool:
        """Check if it is the call of a blocking function."""
        if isinstance(call.parent, nodes.Await):
            # a blocking function can't be called with await
            return False
        call_name = utils.get_call_name(call)
        for regexp in self._blocking_function_names_like:
            if regexp.match(call_name):
                return True
        return False

    def close(self):
        """
        This method is called after checking all .py files.
        """
        self._traverse_blocking_calls(self._calls_of_blocking_functions)

    def _traverse_blocking_calls(
            self, calls_to_traverse: List[nodes.Call], traversed_sequence: Tuple[nodes.Call, ...] = ()
    ) -> None:
        """Make a recursive DFS to traverse the calls trees and find blocking calls"""
        for call in calls_to_traverse:
            if call in traversed_sequence:
                # stop traversal if we found a loop
                continue
            function_def: utils.FunctionDef = call.frame()
            if utils.has_decorator(function_def, decorator_name="thread"):
                # if we reached the @thread decorator - this path can not lead to a blocking call
                continue
            if isinstance(function_def, nodes.AsyncFunctionDef):
                # if the call happens inside an async function, it's a blocking call
                if utils.get_call_node_hash(call) not in self._blocking_calls_hashes:
                    # hash the call node to avoid messages duplicates
                    self._add_blocking_call_message(call, reversed(traversed_sequence))
                    self._blocking_calls_hashes.add(utils.get_call_node_hash(call))
                # stop traversal for this path when found a blocking call
                continue
            self._traverse_blocking_calls(self._get_calls_of_function(function_def), traversed_sequence + (call,))

    def _add_blocking_call_message(self, blocking_call: nodes.Call, calls_sequence: Iterable[nodes.Call]) -> None:
        self.add_message(
            "blocking-call",
            node=blocking_call,
            args=(self._call_sequence_to_str((blocking_call,) + tuple(calls_sequence)),),
        )

    @staticmethod
    def _call_sequence_to_str(calls_sequence: Tuple[nodes.Call, ...]) -> str:
        return " -> ".join(utils.get_call_name(call) for call in calls_sequence)

    def _get_calls_of_function(self, function_def: utils.FunctionDef) -> List[nodes.Call]:
        """Get all the found calls of the function."""
        possible_call_name = utils.get_function_name(function_def)
        return self._all_visited_calls.get(possible_call_name) or []
