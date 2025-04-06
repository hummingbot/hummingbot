import abc
import collections
import copy
import enum
import re

from eth_utils import (
    to_dict,
    to_set,
    to_tuple,
)

from rlp.exceptions import (
    ListDeserializationError,
    ListSerializationError,
    ObjectDeserializationError,
    ObjectSerializationError,
)

from .lists import (
    List,
)


class MetaBase:
    fields = None
    field_names = None
    field_attrs = None
    sedes = None


def _get_duplicates(values):
    counts = collections.Counter(values)
    return tuple(item for item, num in counts.items() if num > 1)


def validate_args_and_kwargs(args, kwargs, arg_names, allow_missing=False):
    duplicate_arg_names = _get_duplicates(arg_names)
    if duplicate_arg_names:
        raise TypeError(f"Duplicate argument names: {sorted(duplicate_arg_names)}")

    needed_kwargs = arg_names[len(args) :]
    used_kwargs = set(arg_names[: len(args)])

    duplicate_kwargs = used_kwargs.intersection(kwargs.keys())
    if duplicate_kwargs:
        raise TypeError(f"Duplicate kwargs: {sorted(duplicate_kwargs)}")

    unknown_kwargs = set(kwargs.keys()).difference(arg_names)
    if unknown_kwargs:
        raise TypeError(f"Unknown kwargs: {sorted(unknown_kwargs)}")

    missing_kwargs = set(needed_kwargs).difference(kwargs.keys())
    if not allow_missing and missing_kwargs:
        raise TypeError(f"Missing kwargs: {sorted(missing_kwargs)}")


@to_tuple
def merge_kwargs_to_args(args, kwargs, arg_names, allow_missing=False):
    validate_args_and_kwargs(args, kwargs, arg_names, allow_missing=allow_missing)

    needed_kwargs = arg_names[len(args) :]

    yield from args
    for arg_name in needed_kwargs:
        yield kwargs[arg_name]


@to_dict
def merge_args_to_kwargs(args, kwargs, arg_names, allow_missing=False):
    validate_args_and_kwargs(args, kwargs, arg_names, allow_missing=allow_missing)

    yield from kwargs.items()
    for value, name in zip(args, arg_names):
        yield name, value


def _eq(left, right):
    """
    Equality comparison that allows for equality between tuple and list types with
    equivalent elements.
    """
    if isinstance(left, (tuple, list)) and isinstance(right, (tuple, list)):
        return len(left) == len(right) and all(_eq(*pair) for pair in zip(left, right))
    else:
        return left == right


class ChangesetState(enum.Enum):
    INITIALIZED = "INITIALIZED"
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class ChangesetField:
    field = None

    def __init__(self, field):
        self.field = field

    def __get__(self, instance, type=None):
        if instance is None:
            return self
        elif instance.__state__ is not ChangesetState.OPEN:
            raise AttributeError(
                "Changeset is not active.  Attribute access not allowed"
            )
        else:
            try:
                return instance.__diff__[self.field]
            except KeyError:
                return getattr(instance.__original__, self.field)

    def __set__(self, instance, value):
        if instance.__state__ is not ChangesetState.OPEN:
            raise AttributeError(
                "Changeset is not active.  Attribute access not allowed"
            )
        instance.__diff__[self.field] = value


class BaseChangeset:
    # reference to the original Serializable instance.
    __original__ = None
    # the state of this fieldset.  Initialized -> Open -> Closed
    __state__ = None
    # the field changes that have been made in this change
    __diff__ = None

    def __init__(self, obj, changes=None):
        self.__original__ = obj
        self.__state__ = ChangesetState.INITIALIZED
        self.__diff__ = changes or {}

    def commit(self):
        obj = self.build_rlp()
        self.close()
        return obj

    def build_rlp(self):
        if self.__state__ == ChangesetState.OPEN:
            field_kwargs = {
                name: self.__diff__.get(name, self.__original__[name])
                for name in self.__original__._meta.field_names
            }
            return type(self.__original__)(**field_kwargs)
        else:
            raise ValueError("Cannot open Changeset which is not in the OPEN state")

    def open(self):
        if self.__state__ == ChangesetState.INITIALIZED:
            self.__state__ = ChangesetState.OPEN
        else:
            raise ValueError(
                "Cannot open Changeset which is not in the INITIALIZED state"
            )

    def close(self):
        if self.__state__ == ChangesetState.OPEN:
            self.__state__ = ChangesetState.CLOSED
        else:
            raise ValueError("Cannot close Changeset which is not in the OPEN state")

    def __enter__(self):
        if self.__state__ == ChangesetState.INITIALIZED:
            self.open()
            return self
        else:
            raise ValueError(
                "Cannot open Changeset which is not in the INITIALIZED state"
            )

    def __exit__(self, exc_type, exc_value, traceback):
        if self.__state__ == ChangesetState.OPEN:
            self.close()


def Changeset(obj, changes):
    namespace = {name: ChangesetField(name) for name in obj._meta.field_names}
    cls = type(
        f"{obj.__class__.__name__}Changeset",
        (BaseChangeset,),
        namespace,
    )
    return cls(obj, changes)


class BaseSerializable(collections.abc.Sequence):
    def __init__(self, *args, **kwargs):
        if kwargs:
            field_values = merge_kwargs_to_args(args, kwargs, self._meta.field_names)
        else:
            field_values = args

        if len(field_values) != len(self._meta.field_names):
            raise TypeError(
                f"Argument count mismatch. expected {len(self._meta.field_names)} - "
                f"got {len(field_values)} - "
                f"missing {','.join(self._meta.field_names[len(field_values) :])}"
            )

        for value, attr in zip(field_values, self._meta.field_attrs):
            setattr(self, attr, make_immutable(value))

    _cached_rlp = None

    def as_dict(self):
        return {field: value for field, value in zip(self._meta.field_names, self)}

    def __iter__(self):
        for attr in self._meta.field_attrs:
            yield getattr(self, attr)

    def __getitem__(self, idx):
        if isinstance(idx, int):
            attr = self._meta.field_attrs[idx]
            return getattr(self, attr)
        elif isinstance(idx, slice):
            field_slice = self._meta.field_attrs[idx]
            return tuple(getattr(self, field) for field in field_slice)
        elif isinstance(idx, str):
            return getattr(self, idx)
        else:
            raise IndexError(f"Unsupported type for __getitem__: {type(idx)}")

    def __len__(self):
        return len(self._meta.fields)

    def __eq__(self, other):
        return isinstance(other, Serializable) and hash(self) == hash(other)

    def __getstate__(self):
        state = self.__dict__.copy()
        # The hash() builtin is not stable across processes
        # (https://docs.python.org/3/reference/datamodel.html#object.__hash__), so we do
        # this here to ensure pickled instances don't carry the cached hash() as that
        # may cause issues like https://github.com/ethereum/py-evm/issues/1318
        state["_hash_cache"] = None
        return state

    _hash_cache = None

    def __hash__(self):
        if self._hash_cache is None:
            self._hash_cache = hash(tuple(self))

        return self._hash_cache

    def __repr__(self):
        keyword_args = tuple(f"{k}={v!r}" for k, v in self.as_dict().items())
        return f"{type(self).__name__}({', '.join(keyword_args)})"

    @classmethod
    def serialize(cls, obj):
        try:
            return cls._meta.sedes.serialize(obj)
        except ListSerializationError as e:
            raise ObjectSerializationError(obj=obj, sedes=cls, list_exception=e)

    @classmethod
    def deserialize(cls, serial, **extra_kwargs):
        try:
            values = cls._meta.sedes.deserialize(serial)
        except ListDeserializationError as e:
            raise ObjectDeserializationError(serial=serial, sedes=cls, list_exception=e)

        args_as_kwargs = merge_args_to_kwargs(values, {}, cls._meta.field_names)
        return cls(**args_as_kwargs, **extra_kwargs)

    def copy(self, *args, **kwargs):
        missing_overrides = (
            set(self._meta.field_names)
            .difference(kwargs.keys())
            .difference(self._meta.field_names[: len(args)])
        )
        unchanged_kwargs = {
            key: copy.deepcopy(value)
            for key, value in self.as_dict().items()
            if key in missing_overrides
        }
        combined_kwargs = dict(**unchanged_kwargs, **kwargs)
        all_kwargs = merge_args_to_kwargs(args, combined_kwargs, self._meta.field_names)
        return type(self)(**all_kwargs)

    def __copy__(self):
        return self.copy()

    def __deepcopy__(self, *args):
        return self.copy()

    _in_mutable_context = False

    def build_changeset(self, *args, **kwargs):
        args_as_kwargs = merge_args_to_kwargs(
            args,
            kwargs,
            self._meta.field_names,
            allow_missing=True,
        )
        return Changeset(self, changes=args_as_kwargs)


def make_immutable(value):
    if isinstance(value, list):
        return tuple(make_immutable(item) for item in value)
    else:
        return value


@to_tuple
def _mk_field_attrs(field_names, extra_namespace):
    namespace = set(field_names).union(extra_namespace)
    for field in field_names:
        while True:
            field = "_" + field
            if field not in namespace:
                namespace.add(field)
                yield field
                break


def _mk_field_property(field, attr):
    def field_fn_getter(self):
        return getattr(self, attr)

    def field_fn_setter(self, value):
        if not self._in_mutable_context:
            raise AttributeError("can't set attribute")
        setattr(self, attr, value)

    return property(field_fn_getter, field_fn_setter)


IDENTIFIER_REGEX = re.compile(r"^[^\d\W]\w*\Z", re.UNICODE)


def _is_valid_identifier(value):
    # Source: https://stackoverflow.com/questions/5474008/regular-expression-to-confirm-whether-a-string-is-a-valid-identifier-in-python  # noqa: E501
    if not isinstance(value, str):
        return False
    return bool(IDENTIFIER_REGEX.match(value))


@to_set
def _get_class_namespace(cls):
    if hasattr(cls, "__dict__"):
        yield from cls.__dict__.keys()
    if hasattr(cls, "__slots__"):
        yield from cls.__slots__


class SerializableBase(abc.ABCMeta):
    def __new__(cls, name, bases, attrs):
        super_new = super().__new__

        serializable_bases = tuple(b for b in bases if isinstance(b, SerializableBase))
        has_multiple_serializable_parents = len(serializable_bases) > 1
        is_serializable_subclass = any(serializable_bases)
        declares_fields = "fields" in attrs

        if not is_serializable_subclass:
            # If this is the original creation of the `Serializable` class,
            # just create the class.
            return super_new(cls, name, bases, attrs)
        elif not declares_fields:
            if has_multiple_serializable_parents:
                raise TypeError(
                    "Cannot create subclass from multiple parent `Serializable` "
                    "classes without explicit `fields` declaration."
                )
            else:
                # This is just a vanilla subclass of a `Serializable` parent class.
                parent_serializable = serializable_bases[0]

                if hasattr(parent_serializable, "_meta"):
                    fields = parent_serializable._meta.fields
                else:
                    # This is a subclass of `Serializable` which has no
                    # `fields`, likely intended for further subclassing.
                    fields = ()
        else:
            # ensure that the `fields` property is a tuple of tuples to ensure
            # immutability.
            fields = tuple(tuple(field) for field in attrs.pop("fields"))

        # split the fields into names and sedes
        if fields:
            field_names, sedes = zip(*fields)
        else:
            field_names, sedes = (), ()

        # check that field names are unique
        duplicate_field_names = _get_duplicates(field_names)
        if duplicate_field_names:
            raise TypeError(
                "The following fields are duplicated in the `fields` "
                f"declaration: {','.join(sorted(duplicate_field_names))}"
            )

        # check that field names are valid identifiers
        invalid_field_names = {
            field_name
            for field_name in field_names
            if not _is_valid_identifier(field_name)
        }
        if invalid_field_names:
            raise TypeError(
                "The following field names are not valid python identifiers: "
                f"{','.join(f'`{item}`' for item in sorted(invalid_field_names))}"
            )

        # extract all of the fields from parent `Serializable` classes.
        parent_field_names = {
            field_name
            for base in serializable_bases
            if hasattr(base, "_meta")
            for field_name in base._meta.field_names
        }

        # check that all fields from parent serializable classes are
        # represented on this class.
        missing_fields = parent_field_names.difference(field_names)
        if missing_fields:
            raise TypeError(
                "Subclasses of `Serializable` **must** contain a full superset "
                "of the fields defined in their parent classes.  The following "
                f"fields are missing: {','.join(sorted(missing_fields))}"
            )

        # the actual field values are stored in separate *private* attributes.
        # This computes attribute names that don't conflict with other
        # attributes already present on the class.
        reserved_namespace = set(attrs.keys()).union(
            attr
            for base in bases
            for parent_cls in base.__mro__
            for attr in _get_class_namespace(parent_cls)
        )
        field_attrs = _mk_field_attrs(field_names, reserved_namespace)

        # construct the Meta object to store field information for the class
        meta_namespace = {
            "fields": fields,
            "field_attrs": field_attrs,
            "field_names": field_names,
            "sedes": List(sedes),
        }

        meta_base = attrs.pop("_meta", MetaBase)
        meta = type(
            "Meta",
            (meta_base,),
            meta_namespace,
        )
        attrs["_meta"] = meta

        # construct `property` attributes for read only access to the fields.
        field_props = tuple(
            (field, _mk_field_property(field, attr))
            for field, attr in zip(meta.field_names, meta.field_attrs)
        )

        return super_new(
            cls,
            name,
            bases,
            dict(field_props + tuple(attrs.items())),
        )


class Serializable(BaseSerializable, metaclass=SerializableBase):
    """
    The base class for serializable objects.
    """
