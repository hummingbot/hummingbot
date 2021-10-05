import asyncio
import unittest
from hummingbot.client.config.config_var import ConfigVar


class ConfigVarTest(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.ev_loop = asyncio.get_event_loop()

    def test_init_defaults_assigned(self):
        var = ConfigVar("key", "test prompt")
        self.assertEqual("key", var.key)
        self.assertEqual("test prompt", var.prompt)
        self.assertEqual(False, var.is_secure)
        self.assertEqual(None, var.default)
        self.assertEqual("str", var.type)
        self.assertTrue(callable(var._required_if))
        self.assertTrue(callable(var._validator))
        self.assertTrue(callable(var._on_validated))
        self.assertFalse(var.prompt_on_new)
        self.assertFalse(var.is_connect_key)
        self.assertIsNone(var.printable_key)

    def test_init_values_assigned(self):
        def fn_a():
            return 1

        def fn_b():
            return 2

        def fn_c():
            return 3
        var = ConfigVar(key="key",
                        prompt="test prompt",
                        is_secure=True,
                        default=1,
                        type_str="int",
                        required_if=fn_a,
                        validator=fn_b,
                        on_validated=fn_c,
                        prompt_on_new=True,
                        is_connect_key=True,
                        printable_key="print_key")
        self.assertEqual("key", var.key)
        self.assertEqual("test prompt", var.prompt)
        self.assertEqual(True, var.is_secure)
        self.assertEqual(1, var.default)
        self.assertEqual("int", var.type)
        self.assertEqual(fn_a, var._required_if)
        self.assertEqual(fn_b, var._validator)
        self.assertEqual(fn_c, var._on_validated)
        self.assertTrue(var.prompt_on_new)
        self.assertTrue(var.is_connect_key)
        self.assertEqual("print_key", var.printable_key)

    def test_get_prompt(self):
        def prompt():
            return "fn prompt"

        async def async_prompt():
            return "async fn prompt"
        var = ConfigVar("key", 'text prompt')
        self.assertEqual("text prompt", asyncio.get_event_loop().run_until_complete(var.get_prompt()))
        var = ConfigVar("key", prompt)
        self.assertEqual("fn prompt", asyncio.get_event_loop().run_until_complete(var.get_prompt()))
        var = ConfigVar("key", async_prompt)
        self.assertEqual("async fn prompt", asyncio.get_event_loop().run_until_complete(var.get_prompt()))

    def test_required(self):
        var = ConfigVar("key", 'prompt', required_if=lambda: True)
        self.assertTrue(var.required)

    def test_required_assertion_error(self):
        var = ConfigVar("key", 'prompt', required_if=True)
        with self.assertRaises(AssertionError):
            var.required

    def test_validate_assertion_errors(self):
        loop = asyncio.get_event_loop()
        var = ConfigVar("key", 'prompt', validator="a")
        with self.assertRaises(AssertionError):
            loop.run_until_complete(var.validate("1"))
        var = ConfigVar("key", 'prompt', validator=lambda v: None, on_validated="a")
        with self.assertRaises(AssertionError):
            loop.run_until_complete(var.validate("1"))

    def test_validate_value_required(self):
        loop = asyncio.get_event_loop()
        var = ConfigVar("key", 'prompt', required_if=lambda: True, validator=lambda v: None)
        self.assertEqual("Value is required.", loop.run_until_complete(var.validate(None)))
        self.assertEqual("Value is required.", loop.run_until_complete(var.validate("")))
        var = ConfigVar("key", 'prompt', required_if=lambda: False, validator=lambda v: None)
        self.assertEqual(None, loop.run_until_complete(var.validate(None)))
        self.assertEqual(None, loop.run_until_complete(var.validate("")))
        self.assertEqual(None, loop.run_until_complete(var.validate(1)))

    def test_validator_functions_called(self):
        def validator(_):
            return "validator error"

        async def async_validator(_):
            return "async validator error"
        loop = asyncio.get_event_loop()
        var = ConfigVar("key", 'prompt', validator=validator)
        self.assertEqual("validator error", loop.run_until_complete(var.validate("a")))
        var = ConfigVar("key", 'prompt', validator=async_validator)
        self.assertEqual("async validator error", loop.run_until_complete(var.validate("a")))

    def test_on_validated_called(self):
        on_validated_txt = ""

        def on_validated(value):
            nonlocal on_validated_txt
            on_validated_txt = value + " on validated"

        async def async_on_validated(value):
            nonlocal on_validated_txt
            on_validated_txt = value + " async on validated"
        loop = asyncio.get_event_loop()
        var = ConfigVar("key", 'prompt', validator=lambda v: None, on_validated=on_validated)
        loop.run_until_complete(var.validate("a"))
        self.assertEqual("a on validated", on_validated_txt)
        on_validated_txt = ""
        var = ConfigVar("key", 'prompt', validator=lambda v: None, on_validated=async_on_validated)
        loop.run_until_complete(var.validate("b"))
        self.assertEqual("b async on validated", on_validated_txt)
        on_validated_txt = ""
        var = ConfigVar("key", 'prompt', validator=lambda v: "validate error", on_validated=async_on_validated)
        loop.run_until_complete(var.validate("b"))
        self.assertEqual("", on_validated_txt)
