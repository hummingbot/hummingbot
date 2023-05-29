from typing import Dict, Optional, Type


class ClassRegistryError(Exception):
    pass


def find_substring_not_in_parent(*, child: str, parent: str) -> Optional[str]:
    """
    Extract an augmentation of parent in child. parent must be completely found
    in child. The augmentation is the part of child that is not found in parent.

    :param child: 'Augmented' string containing all the strings in parent
    :param parent: string containing all the strings to be found in child
    :return: The 'augmentation' of child string based on parent. or None if there are any mismatches

    Example:
        >>> find_substring_not_in_parent("123HeaderGetAccountFooter456", "123HeaderFooter456")
        'GetAccount'
    """
    if child == parent or not child or not parent:
        return None

    if child.startswith(parent):
        return child[len(parent):]

    if child.endswith(parent):
        return child[:len(child) - len(parent)]

    common_prefix_len = 0
    while child[common_prefix_len] == parent[common_prefix_len]:
        common_prefix_len += 1

    common_suffix_len = 0
    while child[-1 - common_suffix_len] == parent[-1 - common_suffix_len]:
        common_suffix_len += 1

    if len(parent) == common_prefix_len + common_suffix_len:
        unique_substring = child[common_prefix_len:-common_suffix_len or None]
        return unique_substring if unique_substring else None

    return None


class ClassRegistry:
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
    __registry: Dict[Type, Dict[str, Type]] = {}

    def __init_subclass__(cls, **kwargs):
        """
        `__init_subclass__` method is called when a subclass is created.

        This method automatically registers any subclass of a ClassRegistry subclass.
        Direct subclasses becomes keys in the dictionary registry.
        Subclasses of direct subclasses are added to the registry for that direct subclass.
        A typical usage would be to define a empty class representing a master type and subclass
        that class to define a collection of similar classes.

        :param cls: The subclass being initialized.
        :param kwargs: Additional keyword arguments.
        """
        super().__init_subclass__(**kwargs)

        # Create the register for any class directly subclassing ClassRegistry
        if ClassRegistry in cls.__bases__:
            if cls not in ClassRegistry.__registry:
                ClassRegistry.__registry[cls] = {}
            else:
                raise ClassRegistryError(f"Class {cls.__name__} already registered")
        else:
            for base in cls.__bases__:
                if issubclass(base, ClassRegistry) and base is not ClassRegistry:
                    class_name = cls.__name__
                    # It's a subclass of a subclass of ClassRegistry, add it to the existing registry
                    if class_name not in ClassRegistry.__registry[base]:
                        ClassRegistry.__registry[base][class_name] = cls
                        short_name: str = find_substring_not_in_parent(child=class_name, parent=base.__name__)
                        if short_name and short_name not in cls.__registry[base]:
                            if short_name not in cls.__registry[base]:
                                ClassRegistry.__registry[base][short_name] = cls
                            else:
                                raise ClassRegistryError(f"Sub-class shortname {short_name} collides with another clas")
                    else:
                        raise ClassRegistryError(
                            f"Sub-class {class_name} already registered under {base.__name__}")

    @classmethod
    def get_registry(cls) -> Dict[str, Type]:
        """Return a copy of the registry to prevent modification."""
        return cls.__registry.get(cls, {}).copy()

    @classmethod
    def find_class_by_name(cls, class_name: str) -> Optional[Type]:
        """Return the class registered under the class_name
        :param class_name: The name of the class to return
        """
        return cls.__registry.get(cls, {}).get(class_name, None)
