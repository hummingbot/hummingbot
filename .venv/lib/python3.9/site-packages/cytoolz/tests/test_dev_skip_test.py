from dev_skip_test import istest, nottest, dev_skip_test

d = {}


@istest
def test_passes():
    d['istest'] = True
    assert True


@nottest
def test_fails():
    d['nottest'] = True
    assert False


def test_dev_skip_test():
    assert dev_skip_test is istest or dev_skip_test is nottest
    assert d.get('istest', False) is True
    assert d.get('nottest', False) is False
