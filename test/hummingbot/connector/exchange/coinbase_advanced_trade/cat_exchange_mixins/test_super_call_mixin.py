import unittest
from abc import ABC, abstractmethod
from typing import Protocol


class MixinProtocol(Protocol):
    """
    Defines the methods that .
    """

    def super_parent_method(self) -> str:
        ...


class _MixinSuperCalls(MixinProtocol):
    def super_parent_method(self):
        return super().parent_method()


class Mixin(_MixinSuperCalls):
    def mixin_calls_super_parent(self):
        return self.super_parent_method(), self.method_defined_in_mixin()

    def method_defined_in_mixin(self):
        return "This method is defined in Mixin"


class Parent(ABC):
    def parent_method(self):
        return "Parent method"

    @abstractmethod
    def must_be_defined_in_class(self):
        pass

    @abstractmethod
    def method_defined_in_mixin(self):
        pass


class A(Mixin, Parent):

    def must_be_defined_in_class(self):
        self.method_defined_in_mixin()
        self.parent_method()
        return "A's method"


class TestA(unittest.TestCase):
    def setUp(self):
        self.test_class = A()

    def test_method_defined_in_a(self):
        result = self.test_class.must_be_defined_in_class()
        self.assertEqual(result, "A's method")

    def test_parent_method(self):
        result = self.test_class.parent_method()
        self.assertEqual(result, "Parent method")

    def test_method_defined_in_mixin(self):
        result = self.test_class.method_defined_in_mixin()
        self.assertEqual(result, "This method is defined in Mixin")

    def test_method_defined_in_mixin_calling_Parent_method(self):
        result = self.test_class.mixin_calls_super_parent()
        self.assertEqual(result, ('Parent method', 'This method is defined in Mixin'))


if __name__ == "__main__":
    unittest.main()
