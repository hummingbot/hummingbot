import unittest
from typing import Dict, Type

from hummingbot.core.utils.class_registry import ClassRegistry, ClassRegistryError, find_substring_not_in_parent


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
        self.assertIn('Derived1', registry[self.MyBase0Class])
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


if __name__ == '__main__':
    unittest.main()
