import logging
import sys
import unittest
from typing import Any, Dict, Type

from pydantic import BaseModel, ValidationError

from hummingbot.core.utils.class_registry import (
    ClassRegistry,
    ClassRegistryError,
    ClassRegistryMetaMixin,
    configure_debug,
    find_substring_not_in_parent,
)


class TestFindSubstringNotInParent(unittest.TestCase):
    def test_empty_strings(self):
        self.assertEqual(None, find_substring_not_in_parent(child="", parent=""))
        self.assertEqual(None, find_substring_not_in_parent(child="test", parent=""))
        self.assertEqual(None, find_substring_not_in_parent(child="", parent="test"))

    def test_no_common_substring(self):
        self.assertEqual(None, find_substring_not_in_parent(child="abc", parent="def"))

    def test_identical_strings(self):
        self.assertEqual(None, find_substring_not_in_parent(child="abc", parent="abc"))

    def test_partial_overlap(self):
        self.assertEqual(None, find_substring_not_in_parent(child="abcdef", parent="defghi"))

    def test_non_identical_strings(self):
        self.assertEqual("GetAccount",
                         find_substring_not_in_parent(child="HeaderGetAccountFooter", parent="HeaderFooter"))

    def test_non_identical_strings_with_common_separators(self):
        self.assertEqual("GetAccount0",
                         find_substring_not_in_parent(child="HeaderGetAccount0Footer", parent="HeaderFooter"))
        self.assertEqual("GetAccount0",
                         find_substring_not_in_parent(child="Header0GetAccount0Footer", parent="Header0Footer"))
        self.assertEqual("GetAccount",
                         find_substring_not_in_parent(child="Header0GetAccount0Footer", parent="Header00Footer"))
        self.assertEqual(None,
                         find_substring_not_in_parent(child="HeaderGetAccountFooter", parent="Header0Footer"))

    def test_non_identical_strings_with_typo(self):
        self.assertEqual(None, find_substring_not_in_parent(child="HeaderGetAccountFooter", parent="HeadersFooter"))

    def test_with_numbers(self):
        self.assertEqual("GetAccount", find_substring_not_in_parent(child="123HeaderGetAccountFooter456",
                                                                    parent="123HeaderFooter456"))

    def test_substring_at_start(self):
        self.assertEqual("GetAccount", find_substring_not_in_parent(child="GetAccountFooter", parent="Footer"))

    def test_substring_at_end(self):
        self.assertEqual("GetAccount", find_substring_not_in_parent(child="HeaderGetAccount", parent="Header"))


class TestClassRegistry(unittest.TestCase):

    def setUp(self):
        class MyBase0Class(ClassRegistry):
            pass

        class MyBase1Class(ClassRegistry):
            pass

        class MyBase0Derived0Class(MyBase0Class):
            pass

        class MyBase0Derived1Class(MyBase0Class):
            pass

        class MyBase0Derived2Class(MyBase0Class):
            pass

        class MyBase1Derived0Class(MyBase1Class):
            pass

        class MyBase1Derived1Class(MyBase1Class):
            pass

        class MyBase1Derived0Derived0Class(MyBase1Derived0Class):
            pass

        class MyBase1Derived0Derived1Class(MyBase1Derived0Class):
            pass

        class MyBase1Derived0Derived2Class(MyBase1Derived0Class):
            pass

        self.MyBase0Class = MyBase0Class
        self.MyBase1Class = MyBase1Class
        self.MyBase0Derived0Class = MyBase0Derived0Class
        self.MyBase0Derived1Class = MyBase0Derived1Class
        self.MyBase0Derived2Class = MyBase0Derived2Class
        self.MyBase1Derived0Class = MyBase1Derived0Class
        self.MyBase1Derived1Class = MyBase1Derived1Class
        self.MyBase1Derived0Derived0Class = MyBase1Derived0Derived0Class
        self.MyBase1Derived0Derived1Class = MyBase1Derived0Derived1Class
        self.MyBase1Derived0Derived2Class = MyBase1Derived0Derived2Class

    def tearDown(self):
        del self.MyBase0Class
        del self.MyBase1Class
        del self.MyBase0Derived0Class
        del self.MyBase0Derived1Class
        del self.MyBase0Derived2Class
        del self.MyBase1Derived0Class
        del self.MyBase1Derived1Class
        del self.MyBase1Derived0Derived0Class
        del self.MyBase1Derived0Derived1Class
        del self.MyBase1Derived0Derived2Class

    def test_subclass_registration_fails_on_existing_short_class_name(self):

        class MyTestClass(ClassRegistry):
            pass

        # Attempting to register a class that has a short_class_name methods raises
        with self.assertRaises(ClassRegistryError):
            class MyTestShortNameClass(MyTestClass):
                @classmethod
                def short_class_name(cls):
                    return "NotCorrect"

    def test_subclass_registration_on_existing_short_class_name(self):

        class MyTestClass(ClassRegistry):
            @classmethod
            def short_class_name(cls):
                return "NotCorrect"

        class MyTestShortNameClass(MyTestClass):
            pass

        # Class correctly registered
        self.assertEqual(MyTestShortNameClass, MyTestClass.get_registry()["ShortName"])
        # Normally, this method should not be called directly, but it should return the correct value
        self.assertEqual("NotCorrect", MyTestClass.short_class_name())
        # This method was created by the registration process
        self.assertTrue(callable(getattr(MyTestShortNameClass, "short_class_name", None)))
        self.assertEqual("ShortName", MyTestShortNameClass.short_class_name())

    def test_subclass_registration(self):
        registry = self.MyBase0Class.get_registry()
        expected_full_names = ['MyBase0Derived0Class', 'MyBase0Derived1Class', 'MyBase0Derived2Class']
        expected_short_names = ['Derived0', 'Derived1', 'Derived2']

        for full_name, short_name in zip(expected_full_names, expected_short_names):
            self.assertIn(full_name, registry)
            self.assertIn(short_name, registry)
            self.assertIs(registry[short_name], registry[full_name])

            # Check that the short_name() method is defined and returns the correct value
            self.assertTrue(hasattr(registry[short_name], "short_class_name"))
            self.assertTrue(short_name, getattr(registry[short_name], "short_class_name")())
        self.assertEqual(len(expected_full_names) + len(expected_short_names), len(registry))

    def test_deep_inheritance(self):
        registry = self.MyBase1Class.get_registry()
        expected_direct_full_names = ['MyBase1Derived0Class', 'MyBase1Derived1Class']
        expected_direct_short_names = ['Derived0', 'Derived1']

        for full_name, short_name in zip(expected_direct_full_names, expected_direct_short_names):
            self.assertIn(full_name, registry)
            self.assertIn(short_name, registry)
            self.assertIs(registry[short_name], registry[full_name])

        expected_second_full_names = ['MyBase1Derived0Derived0Class',
                                      'MyBase1Derived0Derived1Class',
                                      'MyBase1Derived0Derived2Class']
        expected_second_short_names = ['Derived0Derived0', 'Derived0Derived1', 'Derived0Derived2']

        for full_name, short_name in zip(expected_second_full_names, expected_second_short_names):
            self.assertIn(full_name, registry)
            self.assertIn(short_name, registry)
            self.assertIs(registry[short_name], registry[full_name])

        self.assertEqual(len(expected_direct_full_names) +
                         len(expected_direct_short_names) +
                         len(expected_second_full_names) +
                         len(expected_second_short_names), len(registry))

    def test_get_registry_with_class(self):
        registry: Dict[Type, Dict] = ClassRegistry.get_registry()
        self.assertIn(self.MyBase0Class, registry)
        self.assertIn('Derived0', registry[self.MyBase0Class])
        self.assertIn('Derived1', registry[self.MyBase0Class])
        self.assertIn('Derived2', registry[self.MyBase0Class])
        self.assertIn('Derived0Derived1', registry[self.MyBase1Class])

    def test_find_class_by_name(self):
        result = self.MyBase0Class.find_class_by_name('MyBase0Derived0Class')
        self.assertEqual(self.MyBase0Derived0Class, result)
        result = self.MyBase0Class.find_class_by_name('Derived0')
        self.assertEqual(self.MyBase0Derived0Class, result)

        result = self.MyBase1Class.find_class_by_name('MyBase1Derived0Derived0Class')
        self.assertEqual(self.MyBase1Derived0Derived0Class, result)
        result = self.MyBase1Class.find_class_by_name('Derived0Derived0')
        self.assertEqual(self.MyBase1Derived0Derived0Class, result)

    def test_find_class_by_name_not_found(self):
        result = self.MyBase0Class.find_class_by_name('NonExistentClass')
        self.assertIsNone(result)

    def test_duplicate_class_registration(self):
        with self.assertRaises(ClassRegistryError):
            class MyBase0DuplicateDerivedClass(self.MyBase0Class):
                pass

            # This is intentionally demonstrating a duplicate class registration
            # which flake8 would not allow to commit
            class MyBase0DuplicateDerivedClass(self.MyBase0Class):  # noqa: F811
                pass


class TestClassRegistryMixin(unittest.TestCase):
    global indentation

    class MyClassType(ClassRegistry, ClassRegistryMetaMixin, ):
        def my_method(self, value):
            return self.my_sub_attr + value

    class MySubClassType(MyClassType):
        def __init__(self, my_sub_attr=None, **kwargs):
            self.my_sub_attr = my_sub_attr

        def my_sub_method(self, value):
            return self.my_sub_attr + value

    def setUp(self):
        # Set DEBUG logging
        # Set the debug flag in the logging configuration
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
        self.MyClassType = TestClassRegistryMixin.MyClassType
        self.MySubClassType = TestClassRegistryMixin.MySubClassType

    def tearDown(self):
        # Reset the debug flag in the module
        configure_debug(False)

    def test_register_and_retrieve(self):
        # Register a class
        self.assertIn(TestClassRegistryMixin.MyClassType, ClassRegistry.get_registry())
        self.assertIn('MySubClassType', ClassRegistry.get_registry()[self.MyClassType])

        # Retrieve a class
        target_class = self.MyClassType.get_class_by_name('MySubClassType')
        self.assertIs(target_class, self.MySubClassType)

    def test_has_short_class_name(self):
        # Register a class
        self.assertFalse(hasattr(self.MyClassType, 'short_class_name'))

        self.assertTrue(hasattr(self.MySubClassType, 'short_class_name'))
        self.assertEqual(self.MySubClassType.short_class_name(), 'Sub')

    def test_create_instance(self):
        # Create an instance
        instance = self.MyClassType('MySubClassType')
        self.assertIsInstance(instance, self.MySubClassType)

    def test_create_instance_without_mixin(self):
        # Create an instance
        instance = self.MySubClassType()
        self.assertIsInstance(instance, self.MySubClassType)

    def test_create_instance_with_attrs_and_methods(self):
        instance = self.MyClassType('MySubClassType', my_sub_attr=10)
        self.assertEqual(instance.my_sub_attr, 10)

        result = instance.my_method(5)
        self.assertEqual(result, 15)

    def test_create_instance_without_mixin_with_attrs_and_methods(self):
        instance = self.MySubClassType(20)
        self.assertIsInstance(instance, self.MySubClassType)
        self.assertEqual(instance.my_sub_attr, 20)

        result = instance.my_method(10)
        self.assertEqual(result, 30)

    def test_class_not_found(self):
        # Attempt to retrieve a non-existent class
        instance = self.MyClassType.get_class_by_name('NonExistentClass')
        self.assertIsNone(instance)

        # Attempt to create an instance of a non-existent class
        with self.assertRaises(ClassRegistryError):
            self.MyClassType('NonExistentClass')

    def test_correct_string_parsing(self):
        instance = self.MyClassType('MySubClassType')
        self.assertIsInstance(instance, self.MySubClassType)

    def test_incorrect_string_parsing(self):
        with self.assertRaises(ClassRegistryError):
            self.MyClassType('IncorrectClassName')


class TestNonInstantiableType(unittest.TestCase):
    class MyClassType(ClassRegistryMetaMixin, ClassRegistry):
        def my_method(self, value):
            return self.my_attr + value

    class MySubClassType(MyClassType):
        def __init__(self, my_sub_attr=None):
            super().__init__()
            self.my_sub_attr = my_sub_attr

    def setUp(self):
        self.MyClassType = TestNonInstantiableType.MyClassType
        self.MySubClassType = TestNonInstantiableType.MySubClassType

    def test_subclass_can_be_instantiated(self):
        # Check that a subclass can be instantiated normally
        instance = self.MySubClassType()
        self.assertIsInstance(instance, self.MySubClassType)

    def test_base_class_cannot_be_instantiated_directly(self):
        # Check that the base class cannot be instantiated directly
        with self.assertRaises(ClassRegistryError):
            self.MyClassType()

    def test_base_class_can_create_instance_of_subclass(self):
        # Check that the base class can be used to create an instance of a subclass
        instance = self.MyClassType('MySubClassType')
        self.assertIsInstance(instance, self.MySubClassType)

    def test_base_class_can_create_instance_of_subclass_with_kwargs(self):
        # Check that the base class can be used to create an instance of a subclass with keyword arguments
        instance = self.MyClassType('MySubClassType', my_sub_attr='test')
        self.assertIsInstance(instance, self.MySubClassType)
        self.assertEqual(instance.my_sub_attr, 'test')


class TestPydanticSubclasses(unittest.TestCase):
    class _PydanticBase(BaseModel):
        string: str
        integer: int
        double: float
        boolean: bool
        dictionary: Dict[str, Any]

        class Config:
            arbitrary_types_allowed = True

    class PydanticType(ClassRegistry):
        pass

    class PydanticSubClassType(_PydanticBase, PydanticType, ):
        pass

    def setUp(self):
        self.PydanticType = TestPydanticSubclasses.PydanticType
        self.PydanticSubClassType = TestPydanticSubclasses.PydanticSubClassType

    def test_pydantic_subclass_registration(self):
        registry = self.PydanticType.get_registry()
        expected_full_name = 'PydanticSubClassType'
        expected_short_name = 'SubClass'

        self.assertIn(expected_full_name, registry)
        self.assertIn(expected_short_name, registry)
        self.assertIs(registry[expected_short_name], registry[expected_full_name])

    def test_pydantic_subclass_registration_missing(self):
        registry = self.PydanticType.get_registry()
        unexpected_name = 'NonExistentSubClass'

        self.assertNotIn(unexpected_name, registry)

    def test_pydantic_subclass_correct_type(self):
        registry = self.PydanticType.get_registry()
        expected_full_name = 'PydanticSubClassType'

        self.assertIs(registry[expected_full_name], self.PydanticSubClassType)

    def test_pydantic_base_not_registered(self):
        registry = self.PydanticType.get_registry()
        unexpected_name = '_PydanticBase'

        self.assertNotIn(unexpected_name, registry)

    def test_pydantic_type_properties(self):
        obj = self.PydanticSubClassType(string="test", integer=10, double=1.0, boolean=True,
                                        dictionary={"key": "value"})

        self.assertEqual(obj.string, "test")
        self.assertEqual(obj.integer, 10)
        self.assertEqual(obj.double, 1.0)
        self.assertEqual(obj.boolean, True)
        self.assertEqual(obj.dictionary, {"key": "value"})

    def test_pydantic_type_invalid_creation(self):
        with self.assertRaises(ValidationError):
            self.PydanticSubClassType(string="test", integer="invalid_integer", double=1.0, boolean=True,
                                      dictionary={"key": "value"})

    def test_class_registration_after_change(self):
        class MasterClass(ClassRegistry):
            pass

        class OtherSubClassInitializer:
            def __init_subclass__(cls, **kwargs):
                super().__init_subclass__(**kwargs)
                assert hasattr(cls, 'short_class_name')

        class MasterSubClass(MasterClass, OtherSubClassInitializer):
            pass

        with self.assertRaises(AssertionError):
            class UnorderedSubClass(
                OtherSubClassInitializer,
                MasterClass
            ):
                pass


if __name__ == '__main__':
    unittest.main()
