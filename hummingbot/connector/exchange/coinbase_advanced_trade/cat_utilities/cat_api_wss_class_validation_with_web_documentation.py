import asyncio
import inspect
import json
import re
import unittest
from typing import Any, Dict, Type

from bs4 import BeautifulSoup
from pyppeteer import launch


async def get_websocket_documentation(url):
    # Launch the browser and navigate to the page
    browser = await launch(executablePath="/usr/bin/brave-browser", headless=True)
    page = await browser.newPage()
    await page.goto(url)

    # Fetch the page content
    content = await page.content()
    soup = BeautifulSoup(content, 'html.parser')

    channel_dict = {}  # dictionary to store channel name and corresponding JSON

    current_title = None
    current_channel = None

    code_tag = None
    json_name = None

    try:
        for tag in soup.recursiveChildGenerator():
            if tag.name == "h2" and 'class' in tag.attrs and 'anchor' in tag.attrs['class']:
                # This is a title, store it as the current title
                current_title = tag.get_text()
                # New title, reset tag references
                code_tag = None
                json_name = None

            elif tag.name == "p" and code_tag is None:
                # This is a paragraph, check if it contains a channel name
                code_tag = tag.find("code")
                if code_tag and current_title:
                    current_channel = code_tag.string
                    channel_dict[current_channel] = {}

            elif tag.name == "pre" and 'class' in tag.attrs and 'language-json' in tag.attrs['class']:
                json_name = "Request" if json_name is None else "Response"
                channel_dict[current_channel][json_name] = {}
                # This is a code block
                json_str = tag.text

                # Clean up the json_str to ensure it's valid JSON
                match = re.search(r'[\{\[]', json_str)

                if match:
                    json_str = json_str[match.start():]
                    json_str = re.sub(r',\s*}', '}', json_str)
                    json_str = re.sub(r',\s*]', ']', json_str)

                try:
                    json_dict = json.loads(json_str)
                except json.JSONDecodeError as e:
                    print(f"Failed to parse JSON: {e}")
                    continue

                if current_title and current_channel:
                    # We're associating this JSON object with the most recent title and channel name
                    channel_dict[current_channel][json_name] = json_dict
        return channel_dict

    except Exception as e:
        print("An error occurred:", str(e))
        await browser.close()
        return None


class ClassWSSValidationWithWebDocumentation:
    class TestSuite(unittest.TestCase):
        class_under_test = None

        def verify_classes(self, web_definition: Dict[str, Any], cls: Type) -> None:
            # Verify URL match
            web_url = web_definition["url"]
            endpoint_func = getattr(cls, "endpoint")  # get the endpoint property
            endpoint_source = inspect.getsource(endpoint_func.fget)  # get its source code

            endpoint_pattern = re.search(r'return f?"([^"]*)"', endpoint_source)
            if endpoint_pattern is None:
                raise ValueError(f"Could not extract URL pattern from endpoint property in class {cls.__name__}")

            endpoint_pattern = endpoint_pattern.group(1).replace('{self.', ':').replace('}', '')

            cls_url = f"{endpoint_pattern}"
            self.assertTrue(web_url.endswith(cls_url), f"URL mismatch for class {cls.__name__}.\n"
                                                       f"Documentation URL: {web_url}\n"
                                                       f"Class URL: {cls_url}")

            # Verify Method match
            # Get method from the class
            class_method = cls.method.fget(cls)  # Use fget to get property value from class

            # Get method from web definition
            web_method = web_definition.get("method")

            # Check if methods match
            self.assertEqual(
                class_method.value,
                web_method.upper(),
                f"Method mismatch for class {cls.__name__}.\n"
                f"Expected: {class_method.value}\n"
                f"Got: {web_method.upper()}"
            )

            # Verify Query/Body parameters match
            web_params = web_definition["parameters"]
            field_definition = [
                f"{p['name']}: Field({'...' if p['required'] else 'None'}, description='{p['description']}')"
                for p in web_params]
            field_definition = "\n".join(field_definition)

            web_params = {param["name"]: param for param in web_params if
                          param["header"] in ["Query Params", "Body params"]}

            class_params = set(
                name for name, field in cls.__fields__.items() if
                field.field_info.extra is None or not field.field_info.extra.get('extra', {}).get("path_param"))
            web_params_set = {name for name, param in web_params.items()}

            missing_params = class_params - web_params_set
            extra_params = web_params_set - class_params

            self.assertTrue(
                not missing_params and not extra_params,
                f"Params mismatch for class {cls.__name__}.\n"
                f"Missing Params in Class: {extra_params}\n"
                f"Extra Params in Class: {missing_params}"
            )

            # Verify Path parameters match
            web_params = web_definition["parameters"]
            web_params = {param["name"]: param for param in web_params if param["header"] in ["Path Params"]}

            class_params = set(
                name for name, field in cls.__fields__.items() if
                field.field_info.extra is not None and field.field_info.extra.get('extra', {}).get("path_param"))
            web_params_set = {name for name, param in web_params.items()}

            missing_params = class_params - web_params_set
            extra_params = web_params_set - class_params

            self.assertTrue(
                not missing_params and not extra_params,
                f"Params mismatch for class {cls.__name__}.\n"
                f"Missing Params: {missing_params}\n"
                f"Extra Params: {extra_params}"
            )

        def test_documentation(self):
            docstring = inspect.getdoc(self.class_under_test)
            doc_url = re.search(r"https?://[^\s]+", docstring).group(0)

            print(f"Testing documentation for {self.class_under_test.__name__} at {doc_url}")
            if doc_url:
                web_params = asyncio.run(get_websocket_documentation(doc_url))
                self.verify_classes(web_params, self.class_under_test)
