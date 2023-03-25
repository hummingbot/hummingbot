"""
The `WeakSingletonMetaclass` module provides a metaclass for implementing a weak reference to a singleton class.

The `WeakSingletonMetaclass` metaclass ensures that only one instance of a class can exist at any time. It uses a
dictionary to store the instances of each class and weak references to these instances. The instances are cleaned up
when their reference count drops to zero.

This module provides a `WeakSingletonMetaclass` metaclass that can be used to create singleton classes. It also
provides several exceptions for handling errors that may occur when using the metaclass.

Example usage:

    from typing_extensions import Type

    class MyClass(metaclass=WeakSingletonMetaclass):
        def __init__(self, name: str):
            self.name = name

    a = MyClass("foo")
    b = MyClass("bar")

    assert a is b


Module name: weak_singleton_metaclass.py
Module description: A metaclass for implementing a weak reference to a singleton class.
Copyright (c) 2023, Memento "RC" Mori
License: MIT

Author: Memento "RC" Mori
Creation date: 2023/03/20
"""

import abc
import functools
import threading
import weakref
from typing import Dict, TypeVar, Union

from typing_extensions import Type


class ClassNotYetInstantiatedError(Exception):
    """Exception raised when the WeakSingletonMetaclass object is not instantiated."""
    pass


class NoLockForInstanceError(Exception):
    """Exception raised when the WeakSingletonMetaclass object has no lock when it has an instance."""
    pass


class ClassAlreadyInstantiatedError(Exception):
    """Exception raised when the WeakSingletonMetaclass object is not instantiated."""
    pass


T = TypeVar("T", bound="WeakSingletonMetaclass")


class WeakSingletonMetaclass(abc.ABCMeta):
    """Metaclass for implementing a weak reference to singleton class.

    The WeakSingletonMetaclass metaclass ensures that only one instance of a class
    can exist at any time. It uses a dictionary to store the instances of each class.
    """

    _instances: Dict[Type[T], Union[weakref.ref, None]] = {}

    _strict_locks: Dict[Type[T], type(threading.Lock())] = {}
    _master_lock: type(threading.Lock()) = threading.Lock()

    def __call__(cls: Type[T], *args, **kwargs) -> T:
        if cls not in cls._instances:
            with cls._master_lock:
                if cls not in cls._instances:
                    cls._instances[cls] = None
                    cls._strict_locks[cls] = threading.Lock()

        assert cls in cls._strict_locks, f"Class {cls} has no strict lock"
        assert cls in cls._instances, f"Class {cls} has no instance"

        if cls._has_no_instance_or_dead(cls):
            with cls._strict_locks[cls]:
                if cls._has_no_instance_or_dead(cls):
                    instance = super(WeakSingletonMetaclass, cls).__call__(*args, **kwargs)
                    cls._instances[cls] = weakref.ref(instance, functools.partial(cls._finalize, cls=cls))
                    return instance

        assert cls._has_hard_reference(cls), f"Class {cls} has no instance"
        return cls._instances[cls]()

    def is_instantiated(cls) -> bool:
        return cls in cls._instances and cls._instances[cls] is not None and cls._instances[cls]() is not None

    @classmethod
    def _has_instance_only(mcs, cls: Type[T]):
        """Check if the class has been initialized but has no instance"""
        instances = getattr(mcs, "_instances", None)
        return cls in instances and instances[cls] is None

    @classmethod
    def _has_no_instance(mcs, cls: Type[T]):
        """Check if the class has been initialized but has no instance"""
        return mcs._has_instance_only(cls)

    @classmethod
    def _has_no_instance_or_dead(mcs, cls: Type[T]):
        """Check if the class has been initialized but has no instance"""
        return mcs._has_instance_only(cls) or mcs._has_dead_reference(cls)

    @classmethod
    def _has_instance(mcs, cls: Type[T]):
        """Check if the class has an instance"""
        instances = getattr(mcs, "_instances", None)
        return cls in instances and instances[cls] is not None

    @classmethod
    def _has_hard_reference(mcs, cls: Type[T]):
        """Check if the class has a hard reference"""
        instances = getattr(mcs, "_instances", None)
        return mcs._has_instance(cls) and instances[cls]() is not None

    @classmethod
    def _has_dead_reference(mcs, cls: Type[T]):
        """Check if the class has a dead reference"""
        instances = getattr(mcs, "_instances", None)
        return mcs._has_instance(cls) and instances[cls]() is None

    @classmethod
    def _cleanup_when_no_reference(mcs, cls: Type[T]):
        """Clean the references to the class if its weak reference is dead (last instance deleted)"""
        assert mcs._has_dead_reference(cls), "_cleanup_when_no_reference called with no dead reference"
        assert cls in mcs._strict_locks, f"{cls.__name__} not in _strict_locks"
        assert mcs._strict_locks[cls].locked(), "_cleanup_when_no_reference should be called when locked"

        mcs._instances[cls] = None
        if mcs._strict_locks[cls].locked():
            mcs._strict_locks[cls] = threading.Lock()

        assert mcs._has_no_instance(cls), "Instance should be None"

    @staticmethod
    def _finalize(wr_obj: weakref, cls: Type[T]):
        """The reference count dropped to 0, simply set the weakref to None"""
        assert wr_obj() is None, "Weakref should be dead"
        cls._instances[cls] = None
        if cls._strict_locks[cls].locked():
            cls._strict_locks[cls] = threading.Lock()
        assert cls._has_no_instance(cls), "Instance should be None"

    # --- Class testing methods ---
    def __clear(cls: Type[T]):
        """Clear the class attributes (registration of the class as Singleton)
        This method was added for testing purposes only. It should not be used in production code.
        This only simulates the class not being referenced as we cannot delete the instance directly."""
        if cls in cls._instances:
            with cls._strict_locks[cls]:
                if cls in cls._instances:
                    cls._instances[cls] = None
                    cls._strict_locks[cls] = threading.Lock()

    def __lock(cls: Type[T]):
        """Returns the lock for the class.
        This method was added for testing purposes only. It should not be used in production code."""
        if cls in cls._strict_locks:
            return cls._strict_locks[cls]
        else:
            raise ClassNotYetInstantiatedError(f"Class {cls.__name__} not yet instantiated. Nothing to lock")
