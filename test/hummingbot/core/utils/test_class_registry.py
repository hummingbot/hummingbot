import logging
import sys
import unittest
from typing import Dict, Type

from hummingbot.core.utils.class_registry import (
    ClassRegistry,
    ClassRegistryError,
    ClassRegistryMixin,
    configure_debug,
    find_substring_not_in_parent,
    test_logger,
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

    def test_subclass_registration(self):
        registry = self.MyBase0Class.get_registry()
        expected_full_names = ['MyBase0Derived0Class', 'MyBase0Derived1Class', 'MyBase0Derived2Class']
        expected_short_names = ['Derived0', 'Derived1', 'Derived2']

        for full_name, short_name in zip(expected_full_names, expected_short_names):
            self.assertIn(full_name, registry)
            self.assertIn(short_name, registry)
            self.assertIs(registry[short_name], registry[full_name])

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

    class MyClassType(ClassRegistry, ClassRegistryMixin, ):
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
        test_logger.debug(f"{indentation}<-'")
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
    class MyClassType(ClassRegistryMixin, ClassRegistry):
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
        with self.assertRaises(TypeError):
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

    def test_subclass_cannot_create_instance_of_itself(self):
        # Check that a subclass cannot be used to create an instance of itself
        with self.assertRaises(TypeError):
            self.MySubClassType('MySubClassType')


if __name__ == '__main__':
    unittest.main()
