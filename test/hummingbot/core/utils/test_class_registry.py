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
        class MyBaseClass(ClassRegistry):
            pass

        class MyBaseDerivedClass(MyBaseClass):
            pass

        self.MyBaseClass = MyBaseClass
        self.MyDerivedClass = MyBaseDerivedClass

    def tearDown(self):
        del self.MyBaseClass
        del self.MyDerivedClass

    def test_subclass_registration(self):
        registry = self.MyBaseClass.get_registry()
        self.assertIn('MyBaseDerivedClass', registry)
        self.assertIn('Derived', registry)
        self.assertIs(registry['Derived'], registry['MyBaseDerivedClass'])

    def test_get_registry_with_class(self):
        registry: Dict[Type, Dict] = ClassRegistry.get_registry()
        self.assertIn(self.MyBaseClass, registry)
        self.assertIn('Derived', registry[self.MyBaseClass])

    def test_find_class_by_name(self):
        result = self.MyBaseClass.find_class_by_name('MyBaseDerivedClass')
        self.assertEqual(self.MyDerivedClass, result)

    def test_find_class_by_name_short(self):
        result = self.MyBaseClass.find_class_by_name('Derived')
        self.assertEqual(self.MyDerivedClass, result)

    def test_find_class_by_name_not_found(self):
        result = self.MyBaseClass.find_class_by_name('NonExistentClass')
        self.assertIsNone(result)

    def test_duplicate_class_registration(self):
        with self.assertRaises(ClassRegistryError):
            class MyDuplicateBaseDerivedClass(self.MyBaseClass):
                pass

            # This is intentionally demonstrating a duplicate class registration
            # which flake8 would not allow to commit
            class MyDuplicateBaseDerivedClass(self.MyBaseClass):  # noqa: F811

                pass


if __name__ == '__main__':
    unittest.main()
