from .expressions import Expression
def expression(callable, rule_name, grammar):
    """Turn a plain callable into an Expression.

    The callable can be of this simple form::

        def foo(text, pos):
            '''If this custom expression matches starting at text[pos], return
            the index where it stops matching. Otherwise, return None.'''
            if the expression matched:
                return end_pos

    If there child nodes to return, return a tuple::

        return end_pos, children

    If the expression doesn't match at the given ``pos`` at all... ::

        return None

    If your callable needs to make sub-calls to other rules in the grammar or
    do error reporting, it can take this form, gaining additional arguments::

        def foo(text, pos, cache, error, grammar):
            # Call out to other rules:
            node = grammar['another_rule'].match_core(text, pos, cache, error)
            ...
            # Return values as above.

    The return value of the callable, if an int or a tuple, will be
    automatically transmuted into a :class:`~parsimonious.Node`. If it returns
    a Node-like class directly, it will be passed through unchanged.

    :arg rule_name: The rule name to attach to the resulting
        :class:`~parsimonious.Expression`
    :arg grammar: The :class:`~parsimonious.Grammar` this expression will be a
        part of, to make delegating to other rules possible

    """

    # Resolve unbound methods; allows grammars to use @staticmethod custom rules
    # https://stackoverflow.com/questions/41921255/staticmethod-object-is-not-callable
    if ismethoddescriptor(callable) and hasattr(callable, '__func__'):
        callable = callable.__func__

    num_args = len(getfullargspec(callable).args)
    if ismethod(callable):
        # do not count the first argument (typically 'self') for methods
        num_args -= 1
    if num_args == 2:
        is_simple = True
    elif num_args == 5:
        is_simple = False
    else:
        raise RuntimeError("Custom rule functions must take either 2 or 5 "
                           "arguments, not %s." % num_args)

    class AdHocExpression(Expression):
        def _uncached_match(self, text, pos, cache, error):
            result = (callable(text, pos) if is_simple else
                      callable(text, pos, cache, error, grammar))

            if isinstance(result, int):
                end, children = result, None
            elif isinstance(result, tuple):
                end, children = result
            else:
                # Node or None
                return result
            return Node(self, text, pos, end, children=children)

        def _as_rhs(self):
            return '{custom function "%s"}' % callable.__name__

    return AdHocExpression(name=rule_name)
