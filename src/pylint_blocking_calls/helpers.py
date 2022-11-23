from typing import List, Optional, Union

from astroid import nodes

FunctionDef = Union[nodes.FunctionDef, nodes.AsyncFunctionDef]


def has_decorator(function_def: FunctionDef, *, decorator_name: str) -> bool:
    """Check if the function has a decorator with the given name."""
    return any(
        True
        for node in getattr(function_def.decorators, "nodes", [])
        if isinstance(node, nodes.Name) and node.as_string() == decorator_name
    )


def get_function_decorator_names(function_def: FunctionDef) -> List[str]:
    """Get list of decorators which should be ignored"""
    return [
        node.as_string()
        for node in getattr(function_def.decorators, "nodes", [])
        if isinstance(node, nodes.Name)
    ]


def get_call_node_hash(call: nodes.Call) -> str:
    """Get a unique representation of the call node"""
    return repr(call)


def get_call_name(call: nodes.Call) -> Optional[str]:
    """Get the full dotted name of the function being called.

    Replace the `self` and `cls` prefixes with full names of the classes.

    Return None if we can't determine the function name:
        "callable[0]()"
        "".join(...)"

    Return full dotted name of the function in other cases:
        "self.request.get" -> "Handler.request.get"
        "ironic_admin.node.list"
        "get_session_managed"
        "cls.check_limits" -> "ClientQuotasReservation.check_limits"
    """
    # simple case: a function is called directly
    if isinstance(call.func, nodes.Name):
        return call.func.name

    # determine the dotted name of the function like "a.b.c.d"
    call_name_parts = []
    call_func = call.func
    while True:
        if isinstance(call_func, nodes.Attribute):
            call_name_parts.append(call_func.attrname)
            call_func = call_func.expr
        elif isinstance(call_func, nodes.Call):
            call_func = call_func.func
        elif isinstance(call_func, nodes.Name):
            call_name_parts.append(call_func.name)
            break
        else:
            return None
    call_name_parts = list(reversed(call_name_parts))

    # replace "cls" and "self" with the class name
    function_def: FunctionDef = call.frame()
    if function_def.is_method() and call_name_parts[0] in ("self", "cls"):
        class_name = function_def.parent.name  # type: ignore
        call_name_parts[0] = class_name

    return ".".join(call_name_parts)


def get_function_name(function_def: FunctionDef) -> str:
    """Get full dotted name of the function.
    Examples: "get_session_managed", "VolumeMetadataItemHandler.post", etc.
    """
    if function_def.is_method():
        class_name = function_def.parent.name  # type: ignore
        return f"{class_name}.{function_def.name}"
    return function_def.name


def find_module_name(node):
    """Trying to find 'nodes.Module' from given node. Then get name of this module"""
    while not isinstance(node, nodes.Module):
        node = node.parent
    return node.name
