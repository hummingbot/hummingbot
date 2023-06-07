"""
The module provides the following classes:

ClassRegistry: A class registry that allows registering and retrieving classes by name. Subclasses of ClassRegistry
can be registered as keys in the registry, and subclasses of those classes can be added to the registry.

ClassRegistryMixin: A mixin class that provides functionality for retrieving classes from the registry based on their
names. Classes using this mixin should not be instantiated directly. The module also includes supporting classes and
functions for managing class registration and retrieval.

Module name: class_registry.py
Module description: A class registry mechanism for managing and accessing classes based on their names.
Copyright (c) 2023, Memento "RC" Mori
License: MIT
Author: Memento "RC" Mori
Creation date: 2023/05/15
"""

import logging
from abc import ABCMeta
from asyncio import Protocol
from typing import Any, Dict, Optional, Tuple, Type, TypeVar, Union

test_logger = logging.getLogger(__name__)
enable_test_debug = False
indentation = ''


def configure_debug(debug_flag: bool):
    """
    Configure the debug flag.

    :param debug_flag: Flag indicating whether debug mode should be enabled.
    """
    global enable_test_debug
    enable_test_debug = debug_flag

    if enable_test_debug:
        test_logger.setLevel(logging.DEBUG)
    else:
        test_logger.setLevel(logging.INFO)


class ClassRegistryError(Exception):
    """
    Exception class for ClassRegistry-related errors.
    """
    pass


def find_substring_not_in_parent(*, child: str, parent: str) -> Optional[str]:
    """
    Extract an augmentation of parent in child. parent must be completely found
    in child. The augmentation is the part of child that is not found in parent.

    :param child: 'Augmented' string containing all the strings in parent
    :param parent: string containing all the strings to be found in child
    :return: The 'augmentation' of child string based on parent. or None if there are any mismatches

    Example:
        >>> find_substring_not_in_parent(child="123HeaderGetAccountFooter456", parent="123HeaderFooter456")
        'GetAccount'
    """
    # If child and parent are the same, or one of them is empty, return None
    if child == parent or not child or not parent:
        return None

    # If child starts with parent, return the remaining part of child
    if child.startswith(parent):
        return child[len(parent):]

    # If child ends with parent, return the starting part of child
    if child.endswith(parent):
        return child[:len(child) - len(parent)]

    # Initialize counters for common prefix and suffix lengths
    common_prefix_len = 0
    common_suffix_len = 0

    # Count common prefix length
    while child[common_prefix_len] == parent[common_prefix_len]:
        common_prefix_len += 1

    # Count common suffix length
    while all((child[-1 - common_suffix_len] == parent[-1 - common_suffix_len],
               common_suffix_len < len(parent) - common_prefix_len)):
        common_suffix_len += 1

    # If total length of common prefix and suffix matches length of parent, return unique substring in child
    if len(parent) == common_prefix_len + common_suffix_len:
        unique_substring = child[common_prefix_len:-common_suffix_len or None]
        return unique_substring if unique_substring else None

    return None


class RegisterKey(Protocol):
    __class_registry__register_key__: bool


class RegisteredClass(Protocol):
    __class_registry__registered_class__: bool


T = TypeVar("T", bound=RegisterKey)
V = TypeVar("V", bound=RegisteredClass)


class _ClassRegistry:
    """
    Generic Registry indexed on class objects and holding a dictionary of classes
    objects indexed on class names.
    """

    __registry: Dict[Type[T], Dict[str, Type[V]]] = {}

    @classmethod
    def register_master_class(cls, class_obj: Type[T]):
        """
        Register a master class in the registry.

        :param class_obj: The master class to register.
        """
        if class_obj not in cls.__registry:
            cls.__registry[class_obj] = {}
        else:
            raise ClassRegistryError(f"Class {cls.__name__} already registered")

    @classmethod
    def register_sub_class_add_nickname(cls, master_class: Type[T], class_name: str, class_obj: Type[V]):
        """
        Register a subclass with a nickname under a master class in the registry.

        :param master_class: The master class under which to register the subclass.
        :param class_name: The name of the subclass.
        :param class_obj: The subclass to register.
        """
        if master_class in cls.__registry:
            if class_name not in cls.__registry[master_class]:
                cls.__registry[master_class][class_name] = class_obj
                if short_name := find_substring_not_in_parent(child=class_name, parent=master_class.__name__):
                    cls.__registry[master_class][short_name] = class_obj
            else:
                raise ClassRegistryError(f"Sub-Class {class_name} already registered to {master_class.__name__}.")
        else:
            raise ClassRegistryError(
                f"Failed to register Sub-Class {class_name} to unregistered {master_class.__name__}.")

    @staticmethod
    def find_class_by_name(class_type: Type[T], class_name: str) -> Optional[Type[V]]:
        """
        Find a class in the registry by its name.

        :param class_type: Class type of the class to find
        :param class_name: The name of the class to find.
        :return: The class registered under the given name, or None if not found.
        """
        return _ClassRegistry.__registry.get(class_type, {}).get(class_name, None)


class ClassRegistry(_ClassRegistry):
    """
    This class provides a registry for classes that are subclasses of any subclass of `ClassRegistry`.
    It allows retrieving classes based on their names and maintains a registry of class hierarchies.

    ClassRegistry subclasses should be initialized as base classes for the target classes.

    Example:
        A typical usage can be to define an empty class representing a master type and subclass
        that class to define a collection of similar classes. This is very useful in the case of
        NamedTuple classes, which cannot be subclassed directly or implement registry with a metaclass.

        class MyClassType(ClassRegistry):
            pass

        class MySubClass(NamedTuple, MyClassType):
            pass

        registry = MyBaseClass.get_registry()
        my_subclass = registry.get("MySubClass")

    Class Attributes:
        __registry (Dict[Type, Dict[str, Type]]): The registry of classes, organized by base class.

    Methods:
        __init_subclass__(**kwargs): Override of the `__init_subclass__` method to register subclasses.
        find_substring(child: str, parent: str) -> str: Find the substring of `child` not found in `parent`.
        get_registry() -> Dict[str, Type]: Get a copy of the registry to prevent modification.
        find_class_by_name(class_name: str) -> Optional[Type]: Find the class registered under the specified class name.
    """

    def __init_subclass__(cls: Union[Type[T], Type[V]], *args, **kwargs):
        """
        `__init_subclass__` method is called when a subclass is created.

        This method automatically registers any subclass of a ClassRegistry subclass.
        Direct subclasses becomes keys in the dictionary registry.
        Subclasses of direct subclasses are added to the registry for that direct subclass.
        A typical usage would be to define an empty class representing a master type and subclass
        that class to define a collection of similar classes.

        :param cls: The subclass being initialized.
        :param kwargs: Additional keyword arguments.
        """
        super().__init_subclass__(*args, **kwargs)

        # Create the register for any class directly subclassing ClassRegistry
        if ClassRegistry in cls.__bases__:
            if hasattr(cls, "__class_registry__register_key__") and cls.__class_registry__register_key__:
                cls.register_master_class(cls)
            else:
                raise ClassRegistryError(f"Class {cls.__name__} is missing a register key. "
                                         f"It must subclass ClassRegistryMixin along with the ClassRegistry.")
        else:
            for base in cls.__bases__:
                if issubclass(base, ClassRegistry) and base is not ClassRegistry:
                    class_name = cls.__name__
                    if (
                            not hasattr(cls, "__class_registry__registered_class__")
                            or not cls.__class_registry__registered_class__
                    ):
                        raise ClassRegistryError(f"Class {cls.__name__} is missing a register key. "
                                                 f"It must subclass ClassRegistryMixin along with the ClassRegistry.")

                    # Multi-level subclassing, add it to the registry of the base class
                    if base not in ClassRegistry.__registry:
                        for sub_base in base.__bases__:
                            if sub_base in ClassRegistry.__registry:
                                base = sub_base
                                break

                    # It's a subclass of a subclass of ClassRegistry, add it to the existing registry
                    cls.register_sub_class_add_nickname(base, class_name, cls)

    @classmethod
    def get_registry(cls: Union[Type[T], Type[V]]) -> Union[Dict[str, Type[T]], Dict[Type[T], Dict[str, Type[V]]]]:
        """Return a copy of the registry to prevent modification."""
        if cls is ClassRegistry:
            return ClassRegistry.__registry.copy()
        if cls in ClassRegistry.__registry:
            return ClassRegistry.__registry[cls].copy()
        return {}


class _NonInstantiableClassRegistry(ABCMeta):
    """
    Metaclass that prevents instantiation of ClassRegistry key without providing a valid class name.
    A key classe should instantiate one of the classes registered in their register
    """

    def __new__(mcs: Type['_NonInstantiableClassRegistry'],
                name: str,
                bases: Tuple[Type[Any], ...],
                attrs: Dict[str, Any]) -> Any:
        """
        Prevents instantiation of ClassRegistry key without providing a valid class name.
        :param name:
        :param bases:
        :param attrs:
        """
        if bases:
            if ClassRegistryMixin in bases:
                if any(("__init__" in attrs,
                        "__call__" in attrs,
                        "__new__" in attrs,)):
                    raise ClassRegistryError("ClassRegistryMixin sub-classes are not instantiable."
                                             "They cannot define an __init__, __call__ or __new__ methods.")
                attrs["__class_registry__register_key__"] = True
                attrs["__class_registry__registered_class__"] = False
            else:
                if any(("__call__" in attrs,
                        "__new__" in attrs,)):
                    raise ClassRegistryError("ClassRegistryMixin sub-subclasses instantiable, but they cannot"
                                             " define __call__ or __new__ methods.")
                attrs["__class_registry__register_key__"] = False
                attrs["__class_registry__registered_class__"] = True
        return super().__new__(mcs, name, bases, attrs)

    def __call__(cls: Union[Type[T], Type[V]], *args, **kwargs):
        """
        Creates a new instance of a registered class via a key class that has a registered class name.
        Or when the key class instantiate a registered class after removing the first argument or 'class_name'
        keyword argument.

        :param args: Positional arguments passed to the class constructor.
        :param kwargs: Keyword arguments passed to the class constructor.
        :return: The newly created instance of the class.
        :raises ClassRegistryError: If the class is not registered or the class name is not provided.
        """

        if cls.__class_registry__register_key__:
            class_name = kwargs.pop("class_name", None)
            if not class_name and args:
                class_name: str = args[0]
                args: Tuple[Any] = args[1:]

            target_class: Optional[Type[V]] = None
            if (
                    class_name is None
                    or not isinstance(class_name, str)
                    or (target_class := ClassRegistry.find_class_by_name(cls, class_name)) is None
            ):
                raise ClassRegistryError(f"Type {cls.__name__} cannot be called:{cls.__name__}() without a class name"
                                         f" or with an unregistered class name ({class_name}).")

            instance = target_class.__new__(target_class)
            if isinstance(instance, target_class):
                target_class.__init__(instance, *args, **kwargs)  # type: ignore
            return instance

        instance = super().__call__(*args, **kwargs)
        return instance


U = TypeVar('U', bound='ClassRegistryMixin')


class ClassRegistryMixin(metaclass=_NonInstantiableClassRegistry):
    """
    Mixin class that provides functionality for retrieving classes from the registry
    based on their names.
    """
    def __init__(self, *args, **kwargs):
        raise ClassRegistryError("ClassRegistryMixin sub-classes are not instantiable.")

    @classmethod
    def get_class_by_name(cls: Type[T], class_name: str) -> Optional[Type[V]]:
        """
        Get a class from the registry based on its name.

        :param class_name: The name of the class to retrieve.
        :return: The class registered under the given name, or None if not found.
        """
        return ClassRegistry.find_class_by_name(cls, class_name)
