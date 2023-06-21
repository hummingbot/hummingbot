import copy
import json
import random
import re
from typing import Any, Dict, Optional, Protocol, Type

from pydantic import BaseModel, ValidationError
from typing_extensions import runtime_checkable


def extract_json_from_docstring(docstring: str) -> Optional[Dict]:
    """
    Extracts JSON from the docstring.

    :param docstring: The docstring to extract JSON from.
    :return: The extracted JSON dictionary, or None if JSON is not found.
    """
    if docstring is None:
        return None
    json_match = re.search(r'```json\s*(\{.*?\})\s*```', docstring, re.DOTALL)
    if json_match:
        try:
            json_struct = json.loads(json_match.group(1), strict=False)
        except json.JSONDecodeError:
            return None
        return json_struct
    else:
        return None


class DictMethodJsonProtocol(Protocol):
    """
    Protocol defining the requirements of a mockable from JSON class
    """

    def __call__(self, **kwargs) -> "DictMethodJsonProtocol":
        ...

    @classmethod
    def to_dict_for_json(cls) -> Dict[str, Any]:
        """
        Returns a dictionary representation of the class, suitable for JSON serialization.
        Enums must be transformed to their values, Tuples to lists, etc.
        """
        ...


class _DictClsProtocol(DictMethodJsonProtocol):
    @classmethod
    def _substitute_with(cls: "_DictClsProtocol", model_dict, substitutes) -> Dict[str, Any]:
        ...

    @classmethod
    def _sample_for_field(cls,
                          field: str,
                          field_class: Type,
                          json_struct: Dict[str, Any],
                          subs: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        ...

    @classmethod
    def _sample_for_class(cls,
                          json_struct: Dict[str, Any],
                          subs: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        ...

    @classmethod
    def _instantiate(cls: DictMethodJsonProtocol,
                     sample: Dict[str, Any]) -> DictMethodJsonProtocol:
        ...

    @classmethod
    def _instantiate_to_dict(cls: DictMethodJsonProtocol,
                             sample: Dict[str, Any]) -> Dict[str, Any]:
        ...

    @classmethod
    def dict_sample_from_json_docstring(cls: "_DictClsProtocol",
                                        substitutes: Dict = None) -> Optional[Dict[str, Any]]:
        ...


class _BaseJsonDocMixin:
    @classmethod
    def _substitute_with(cls, model_dict, substitutes) -> Dict[str, Any]:
        """
        Substitute values in the model dictionary with the provided substitutes.

        :param model_dict: The model dictionary to substitute values in.
        :param substitutes: The dictionary of substitutes to use.
        :return: The model dictionary with substituted values.
        """
        if substitutes is None:
            substitutes = {}
        if isinstance(model_dict, dict):
            for k, v in model_dict.items():
                if k in substitutes:
                    if isinstance(substitutes[k], list) and isinstance(v, (list, tuple)):
                        model_dict[k] = cls._substitute_with(model_dict[k], substitutes[k])
                    elif isinstance(substitutes[k], dict) and isinstance(v, dict):
                        model_dict[k] = cls._substitute_with(v, substitutes[k])
                    else:
                        model_dict[k] = substitutes[k]
                    substitutes.pop(k)

        elif isinstance(model_dict, list):
            # Handle adding and removing of tuple entries
            if len(model_dict) < len(substitutes):
                model_dict.extend([copy.deepcopy(model_dict[-1]) for _ in range(len(substitutes) - len(model_dict))])
            elif len(model_dict) > len(substitutes):
                model_dict = model_dict[:len(substitutes)]
            model_dict = [cls._substitute_with(item, replace)
                          for i, (item, replace) in enumerate(zip(model_dict, substitutes))]
        return model_dict

    @classmethod
    def _sample_for_field(cls,
                          field: str,
                          field_class: Type,
                          json_struct: Dict[str, Any],
                          subs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate a sample value for a field based on its class and the provided JSON structure.

        :param field: The name of the field.
        :param field_class: The class of the field.
        :param json_struct: The JSON structure to use for generating the sample.
        :return: The sample value for the field.
        """
        if subs is None:
            subs = {}
        if isinstance(field_class, type) and issubclass(field_class, DictMethodMockableFromJsonProtocol):
            field_class_sample = field_class.dict_sample_from_json_docstring(subs.get(field, None))
            return field_class_sample
        return json_struct[field]

    @classmethod
    def _sample_for_class(cls,
                          json_struct: Dict[str, Any],
                          subs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate a sample dictionary for the class based on the provided JSON structure.

        :param json_struct: The JSON structure to use for generating the sample.
        :return: The sample dictionary for the class.
        """

        def get_all_annotations(cls):
            annotations = {}
            for base in reversed(cls.__mro__):
                if issubclass(base, BaseModel):
                    annotations.update(getattr(base, '__annotations__', {}))
            return annotations

        if subs is None:
            subs = {}
        field_samples_dict = {}
        for field, field_class in get_all_annotations(cls).items():
            field_samples_dict[field] = cls._sample_for_field(field, field_class, json_struct, subs)
        return field_samples_dict

    @classmethod
    def _instantiate(cls: DictMethodJsonProtocol, sample: Dict[str, Any]) -> DictMethodJsonProtocol:
        """
        Creates a sample dictionary from a JSON docstring. The sample comes from the instantiation of
        the class and its formatting method to_dict_for_json()

        :param cls: The class to create the sample dictionary for.
        :param sample: Dictionary of the sample to instantiate the class.
        :return: The sample dictionary generated from the JSON docstring.
        :raises TypeError: If the sample dictionary is not valid for the class.
        """
        try:
            instance: DictMethodJsonProtocol = cls(**sample)
            return instance
        except ValidationError as e:
            print(f"Error creating sample dictionary from JSON docstring for class {cls.__name__}: {e}"
                  f"\n\tSample dictionary: {sample}")
            raise e
        except TypeError as e:
            print(f"Error creating sample dictionary from JSON docstring for class {cls.__name__}: {e}")
            raise e

    @classmethod
    def _instantiate_to_dict(cls: _DictClsProtocol, sample: Dict[str, Any]) -> Dict[str, Any]:
        """
        Creates a sample dictionary from a JSON docstring. The sample comes from the instantiation of
        the class and its formatting method to_dict_for_json()

        :param cls: The class to create the sample dictionary for.
        :param sample: Dictionary of the sample to instantiate the class.
        :return: The sample dictionary generated from the JSON docstring.
        :raises TypeError: If the sample dictionary is not valid for the class.
        """
        return cls._instantiate(sample).to_dict_for_json()

    @classmethod
    def json_sample_from_json_docstring(cls: _DictClsProtocol,
                                        substitutes: Optional[Dict] = None) -> Optional[str]:
        """
        Creates a sample JSON from a JSON docstring.

        :param cls: The class to create the sample dictionary for.
        :param substitutes: Dictionary of substitutes for testing purposes. Defaults to None.
        :return: The sample dictionary generated from the JSON docstring.
        """
        json_string: str = json.dumps(cls.dict_sample_from_json_docstring(substitutes))
        return json_string


@runtime_checkable
class DictMethodMockableFromJsonProtocol(Protocol):
    @classmethod
    def dict_sample_from_json_docstring(
            cls: _DictClsProtocol,
            substitutes: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """
        Returns a dictionary sample from JSON docstring
        """
        ...


class DictMethodMockableFromJsonDocMixin(_BaseJsonDocMixin):
    """
    Mixin class that provides functionality for creating a sample dictionary from JSON
    data (```json ...```) in the docstrings.

    Subclasses using this mixin should implement the `dict()` method returning a dictionary
    representation of the class. The substitutes parameter can be used to substitute
    values in the dictionary for testing purposes.

    Example usage:

        class MyClass(DictMethodMockableFromJsonDocMixin):
        json_doc = '''
        {
            "key1": "value1",
            "key2": "value2"
        }
        '''
        sample = MyClass.dict_sample_from_json_docstring()

    """

    @classmethod
    def dict_sample_from_json_docstring(
            cls: _DictClsProtocol,
            substitutes: Dict = None) -> Optional[Dict[str, Any]]:
        """
        Creates a sample dictionary from a JSON docstring.

        :param cls: The class to create the sample dictionary for.
        :param substitutes: Dictionary of substitutes for testing purposes. Defaults to None.
        :return: The sample dictionary generated from the JSON docstring.
        """
        json_struct = extract_json_from_docstring(cls.__doc__)
        if json_struct is None:
            print(f"No JSON found in the docstring of class {cls.__name__}")
            return None

        field_samples_dict = cls._sample_for_class(json_struct, substitutes)
        d: Dict[str, Any] = cls._instantiate_to_dict(field_samples_dict)
        d = cls._substitute_with(d, substitutes)
        return d


class DictMethodMockableFromJsonOneOfManyDocMixin(_BaseJsonDocMixin):
    """
    Mixin class that provides functionality for creating a sample dictionary from JSON
    data (```json ...```) in the docstrings.

    Subclasses using this mixin should implement the `dict()` method returning a dictionary
    representation of the class. The substitutes parameter can be used to substitute
    values in the dictionary for testing purposes.

    Example usage:

        class MyClass(DictMethodMockableFromJsonDocMixin):
        json_doc = '''
        {
            "option1": {
                "key1": "value1",
                "key2": "value2"
            },
            "option2": {
                "key1": "value1",
                "key2": "value2"
            }
        }
        '''
        sample = MyClass.dict_sample_from_json_docstring()

    """

    @classmethod
    def dict_sample_from_json_docstring(
            cls: _DictClsProtocol,
            substitutes: Dict = None) -> Optional[Dict[str, Any]]:
        """
        Creates a sample dictionary from a JSON docstring.

        :param cls: The class to create the sample dictionary for.
        :param substitutes: Dictionary of substitutes for testing purposes. Defaults to None.
        :return: The sample dictionary generated from the JSON docstring.
        """
        json_struct = extract_json_from_docstring(cls.__doc__)
        if json_struct is None:
            print(f"No JSON found in the docstring of class {cls.__name__}")
            return None

        if substitutes is not None:
            if (
                    len(substitutes.keys()) != 1 or
                    list(substitutes.keys())[0] not in json_struct.keys()
            ):
                raise TypeError(f"Invalid substitutes for JSON docstring for class {cls.__name__}")
            field = list(substitutes.keys())[0]
        else:
            field = random.choice(list(json_struct.keys()))

        field_class = cls.__annotations__[field]
        single_field_json_struct = cls._sample_for_field(field, field_class, json_struct, substitutes)

        d: Dict[str, Any] = cls._instantiate_to_dict({field: single_field_json_struct})
        d: Dict[str, Any] = cls._substitute_with(d, substitutes)
        return d
