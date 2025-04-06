"""Provide an asynchronous equivalent *to exec*."""

import ast
import codeop
from io import StringIO
from tokenize import generate_tokens, STRING, TokenError

CORO_NAME = "__corofn"
CORO_DEF = f"async def {CORO_NAME}(): "
CORO_CODE = CORO_DEF + "return (None, locals())\n"


def make_arg(key, annotation=None):
    """Make an ast function argument."""
    arg = ast.arg(key, annotation)
    arg.lineno, arg.col_offset = 0, 0
    return arg


def full_update(dct, values):
    """Fully update a dictionary."""
    dct.clear()
    dct.update(values)


def exec_single_result(obj, local, stream):
    """Reproduce the exec behavior in single mode (print and builtins._)"""
    local["_"] = obj
    if obj is not None:
        print(repr(obj), file=stream)


class ReturnChecker(ast.NodeVisitor):
    def __init__(self, filename):
        super().__init__()
        self.filename = filename

    def visit_FunctionDef(self, node: ast.FunctionDef):
        return  # skip functions

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        return  # async functions too

    def visit_Return(self, node: ast.Return):
        raise SyntaxError(
            "'return' outside function",
            (self.filename, node.lineno, node.col_offset + 1, None),
        )

    def visit_Yield(self, node: ast.Yield):
        raise SyntaxError(
            "'yield' outside function",
            (self.filename, node.lineno, node.col_offset + 1, None),
        )

    def visit_YieldFrom(self, node: ast.YieldFrom):
        self.visit_Yield(node)  # handle in the same way as regular yield


def make_tree(statement, filename, mode):
    """Helper for *aexec*."""
    # Check for returns and yields
    ReturnChecker(filename).visit(statement)

    # Create tree
    tree = ast.parse(CORO_CODE, filename, "single")
    # Check expression statement
    if isinstance(statement, ast.Expr):
        tree.body[0].body[0].value.elts[0] = statement.value
    else:
        tree.body[0].body.insert(0, statement)
    # Check the coroutine function
    exec(compile(tree, filename, "single"))

    if mode == "exec":
        return ast.Module([tree])
    if mode == "single":
        return ast.Interactive([tree])
    assert mode == "eval"
    raise ValueError("Mode 'eval' is not supported")


def make_coroutine_from_tree(wrapped, filename, local):
    """Make a coroutine from a tree structure."""
    dct = {}
    tree = wrapped.body[0]
    tree.body[0].args.args = list(map(make_arg, local))
    exec(compile(tree, filename, "single"), dct)
    return dct[CORO_NAME](**local)


def get_non_indented_lines(source):
    try:
        for token in generate_tokens(StringIO(source).readline):
            if token.type == STRING:
                # .start and .end line numbers are one-indexed
                yield from range(token.start[0], token.end[0])
    except TokenError:
        pass


def compile_for_aexec(
    source, filename, mode, dont_imply_dedent=False, local={}, **kwargs
):
    """Return a list of (coroutine object, abstract base tree)."""
    flags = ast.PyCF_ONLY_AST
    if dont_imply_dedent:
        flags |= codeop.PyCF_DONT_IMPLY_DEDENT
        # This flag is not available for python before 3.10
        try:
            flags |= codeop.PyCF_ALLOW_INCOMPLETE_INPUT
        except AttributeError:
            pass

    # Avoid a syntax error by wrapping code with `async def`
    # Disabling indentation inside multiline strings
    non_indented = set(  # sets are faster for `in` operation
        get_non_indented_lines(source)
    )
    indented = "\n".join(
        (" " * 4 if i not in non_indented and line else "") + line
        for i, line in enumerate(source.split("\n"))
    )
    coroutine = CORO_DEF + "\n" + indented + "\n"

    # Compilation is always performed in single mode
    compiled = compile(coroutine, filename, "single", flags)
    statements = compiled.body[0].body

    # Use original source to detect missing newlines, depending on the mode
    try:
        compile(source, filename, mode, flags)
    except SyntaxError:
        raise

    return [make_tree(statement, filename, mode) for statement in statements]


async def aexec(source, local=None, stream=None, filename="<aexec>"):
    """Asynchronous equivalent to *exec*."""
    if local is None:
        local = {}
    if isinstance(source, str):
        source = compile_for_aexec(source, filename, "exec")
    for tree in source:
        coro = make_coroutine_from_tree(tree, filename, local=local)
        result, new_local = await coro
        if isinstance(tree, ast.Interactive):
            exec_single_result(result, new_local, stream)
        full_update(local, new_local)


async def aeval(source, local=None):
    """Asynchronous equivalent to *eval*."""
    if local is None:
        local = {}

    if not isinstance(local, dict):
        raise TypeError("globals must be a dict")

    # Ensure that the result key is unique within the local namespace
    key = "__aeval_result__"
    while key in local:
        key += "_"

    # Perform syntax check to ensure the input is a valid eval expression
    try:
        ast.parse(source, mode="eval")
    except SyntaxError:
        raise

    # Assign the result of the expression to a known variable
    wrapped_code = f"{key} = {source}"

    # Use aexec to evaluate the wrapped code within the given local namespace
    await aexec(wrapped_code, local=local)

    # Return the result from the local namespace
    return local.pop(key)
