# import asyncio
# import inspect
# import re
# import unittest
# from typing import Any, Dict, Type
#
# from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_v3_request_types import (
#     CoinbaseAdvancedTradeCancelOrdersRequest,
#     CoinbaseAdvancedTradeCreateOrderRequest,
#     CoinbaseAdvancedTradeGetAccountRequest,
#     CoinbaseAdvancedTradeGetMarketTradesRequest,
#     CoinbaseAdvancedTradeGetOrderRequest,
#     CoinbaseAdvancedTradeGetProductCandlesRequest,
#     CoinbaseAdvancedTradeGetProductRequest,
#     CoinbaseAdvancedTradeGetTransactionSummaryRequest,
#     CoinbaseAdvancedTradeListAccountsRequest,
#     CoinbaseAdvancedTradeListFillsRequest,
#     CoinbaseAdvancedTradeListOrdersRequest,
#     CoinbaseAdvancedTradeListProductsRequest,
# )
import unittest

from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_v3_request_types import (
    CoinbaseAdvancedTradeRequestType,
)

# from hummingbot.connector.exchange.coinbase_advanced_trade.cat_utilities.cat_api_v3_class_validation_with_web_documentation import (
#     ClassValidationWithWebDocumentation,
# )
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_utilities.cat_class_validation_from_json_docstring import (
    ClassValidationFromJsonDocstring,
)

# from pyppeteer import launch
# from pyppeteer.element_handle import ElementHandle


# async def get_page_content(url):
#     browser = await launch(executablePath="/usr/bin/brave-browser", headless=True)
#     page = await browser.newPage()
#     await page.goto(url)
#
#     try:
#         title_element = await page.querySelector(".apiDocHeader_igJF h1")
#         title_value = await page.evaluate("(element) => element.textContent", title_element)
#
#         # Find the HTTP method element
#         method_element: ElementHandle = await page.querySelector(".apiMethod_J3LC")
#         # pprint(method_element.asElement().__dict__)
#         method_value = await page.evaluate("(element) => element.textContent", method_element)
#
#         # Find the URL element
#         url_element = await page.querySelector(".apiUrl_z6Fn")
#         url_value = await page.evaluate("(element) => element.getAttribute('title')", url_element)
#
#         # Find all the header elements
#         header_elements = await page.querySelectorAll(".sectionHeader_MBwC")
#
#         # Find all the section elements
#         section_elements = await page.querySelectorAll(".sectionContent_tgvO")
#
#         parameters = []
#         for header_element, section_element in zip(header_elements, section_elements):
#             # Extract the header value
#             header_value = await page.evaluate("(element) => element.textContent", header_element)
#             # Get the parameter elements within the section
#             parameter_elements = await section_element.querySelectorAll(".paramItem_Izrs")
#
#             for element in parameter_elements:
#                 # Extract parameter details
#                 description_element = await element.querySelector(".paramDescription_Jrcs p")
#
#                 if description_element:
#                     description = await page.evaluate("(element) => element.textContent", description_element)
#                 else:
#                     description = None
#
#                 name_element = await element.querySelector(".paramName_MlmJ")
#                 type_element = await element.querySelector(".paramType_HWMI")
#                 required_element = await element.querySelector(".paramRequired_Dtof")
#
#                 name = await page.evaluate("(element) => element.textContent", name_element)
#                 parameter_type = await page.evaluate("(element) => element.textContent", type_element)
#                 is_required = await page.evaluate("(element) => element.textContent",
#                                                   required_element) if required_element else None
#
#                 # Append parameter details to the list along with the associated header value
#                 parameters.append({
#                     "name": name.strip(),
#                     "type": parameter_type.strip(),
#                     "required": is_required.strip() == "required" if is_required else False,
#                     "header": header_value.strip(),
#                     "description": description.strip() if description else ""
#                 })
#
#             parameter_elements = await section_element.querySelectorAll(".listItem_mkJa")
#
#             for element in parameter_elements:
#                 # Extract parameter details from the list
#                 description = None
#
#                 description_element = await element.querySelector(".propertyContent_FDlX p")
#                 if description_element:
#                     description = await page.evaluate("(element) => element.textContent", description_element)
#
#                 description_element = await element.querySelectorAll(".propertyContent_FDlX > div")
#                 if len(description_element) > 1 and description is None:
#                     description_element = description_element[1]
#                     description = await page.evaluate("(element) => element.textContent", description_element)
#
#                     # Extract possible values and modify them if present
#                     possible_values_match = re.search(r'Possible values: \[\s*(.*?)\s*\]', description)
#                     if possible_values_match:
#                         possible_values_str = possible_values_match.group(1)
#                         description = re.sub(r'Possible values: \[(.*?)\]', f'Possible values: [{possible_values_str}]', description)
#
#                 name_element = await element.querySelector(".paramHeader_i_6k strong")
#                 type_element = await element.querySelector(".paramType_KuQf")
#                 required_element = await element.querySelector(".paramRequired_gO2B")
#
#                 name = await page.evaluate("(element) => element.textContent", name_element)
#                 parameter_type = await page.evaluate("(element) => element.textContent", type_element)
#                 is_required = await page.evaluate("(element) => element.textContent",
#                                                   required_element) if required_element else None
#
#                 # Append parameter details to the list along with the associated header value
#                 parameters.append({
#                     "name": name.strip(),
#                     "type": parameter_type.strip(),
#                     "required": is_required.strip() == "required" if is_required else False,
#                     "header": header_value.strip(),
#                     "description": description.strip() if description else ""
#                 })
#
#         await browser.close()
#
#         return {
#             "header": title_value.strip(),
#             "method": method_value.strip().lower(),
#             "url": url_value.strip(),
#             "parameters": parameters
#         }
#
#     except Exception as e:
#         print("An error occurred:", str(e))
#         await browser.close()
#         return None
#
#
# class TestDocumentation(unittest.TestCase):
#     def verify_classes(self, web_definition: Dict[str, Any], cls: Type) -> None:
#         # Verify URL match
#         web_url = web_definition["url"]
#         endpoint_func = getattr(cls, "endpoint")  # get the endpoint property
#         endpoint_source = inspect.getsource(endpoint_func.fget)  # get its source code
#
#         endpoint_pattern = re.search(r'return f?"([^"]*)"', endpoint_source)
#         if endpoint_pattern is None:
#             raise ValueError(f"Could not extract URL pattern from endpoint property in class {cls.__name__}")
#
#         endpoint_pattern = endpoint_pattern.group(1).replace('{self.', ':').replace('}', '')
#
#         cls_url = f"{endpoint_pattern}"
#         self.assertTrue(web_url.endswith(cls_url), f"URL mismatch for class {cls.__name__}.\n"
#                                                    f"Documentation URL: {web_url}\n"
#                                                    f"Class URL: {cls_url}")
#
#         # Verify Method match
#         # Get method from the class
#         class_method = cls.method.fget(cls)  # Use fget to get property value from class
#
#         # Get method from web definition
#         web_method = web_definition.get("method")
#
#         # Check if methods match
#         self.assertEqual(
#             class_method.value,
#             web_method.upper(),
#             f"Method mismatch for class {cls.__name__}.\n"
#             f"Expected: {class_method.value}\n"
#             f"Got: {web_method.upper()}"
#         )
#
#         # Verify Query/Body parameters match
#         web_params = web_definition["parameters"]
#         field_definition = [f"{p['name']}: Field({'...' if p['required'] else 'None'}, description='{p['description']}')"
#                             for p in web_params]
#         field_definition = "\n".join(field_definition)
#
#         web_params = {param["name"]: param for param in web_params if
#                       param["header"] in ["Query Params", "Body params"]}
#
#         class_params = set(
#             name for name, field in cls.__fields__.items() if
#             field.field_info.extra is None or not field.field_info.extra.get('extra', {}).get("path_param"))
#         web_params_set = {name for name, param in web_params.items()}
#
#         missing_params = class_params - web_params_set
#         extra_params = web_params_set - class_params
#
#         self.assertTrue(
#             not missing_params and not extra_params,
#             f"Params mismatch for class {cls.__name__}.\n"
#             f"Missing Params in Class: {extra_params}\n"
#             f"Extra Params in Class: {missing_params}"
#         )
#
#         # Verify Path parameters match
#         web_params = web_definition["parameters"]
#         web_params = {param["name"]: param for param in web_params if param["header"] in ["Path Params"]}
#
#         class_params = set(
#             name for name, field in cls.__fields__.items() if
#             field.field_info.extra is not None and field.field_info.extra.get('extra', {}).get("path_param"))
#         web_params_set = {name for name, param in web_params.items()}
#
#         missing_params = class_params - web_params_set
#         extra_params = web_params_set - class_params
#
#         self.assertTrue(
#             not missing_params and not extra_params,
#             f"Params mismatch for class {cls.__name__}.\n"
#             f"Missing Params: {missing_params}\n"
#             f"Extra Params: {extra_params}"
#         )
#
#     def test_list_accounts(self):
#         docstring = inspect.getdoc(CoinbaseAdvancedTradeListAccountsRequest)
#         doc_url = re.search(r"https?://[^\s]+", docstring).group(0)
#
#         web_params = asyncio.run(get_page_content(doc_url))
#
#         self.verify_classes(web_params, CoinbaseAdvancedTradeListAccountsRequest)
#
#     def test_get_account(self):
#         docstring = inspect.getdoc(CoinbaseAdvancedTradeGetAccountRequest)
#         doc_url = re.search(r"https?://[^\s]+", docstring).group(0)
#
#         web_params = asyncio.run(get_page_content(doc_url))
#
#         self.verify_classes(web_params, CoinbaseAdvancedTradeGetAccountRequest)
#
#     def test_create_order(self):
#         docstring = inspect.getdoc(CoinbaseAdvancedTradeCreateOrderRequest)
#         doc_url = re.search(r"https?://[^\s]+", docstring).group(0)
#
#         # web_params = asyncio.run(get_page_content(doc_url))
#
#         # TODO: This test fails because the documentation specifies that all the order_configuration are present
#         #  in the body, but the actual implementation assumes only one configuration is specified at a time.
#         # self.verify_classes(web_params, CoinbaseAdvancedTradeCreateOrderRequest)
#
#     def test_cancel_orders(self):
#         docstring = inspect.getdoc(CoinbaseAdvancedTradeCancelOrdersRequest)
#         doc_url = re.search(r"https?://[^\s]+", docstring).group(0)
#
#         web_params = asyncio.run(get_page_content(doc_url))
#
#         self.verify_classes(web_params, CoinbaseAdvancedTradeCancelOrdersRequest)
#
#     def test_list_orders(self):
#         docstring = inspect.getdoc(CoinbaseAdvancedTradeListOrdersRequest)
#         doc_url = re.search(r"https?://[^\s]+", docstring).group(0)
#
#         web_params = asyncio.run(get_page_content(doc_url))
#
#         self.verify_classes(web_params, CoinbaseAdvancedTradeListOrdersRequest)
#
#     def test_list_fills(self):
#         docstring = inspect.getdoc(CoinbaseAdvancedTradeListFillsRequest)
#         doc_url = re.search(r"https?://[^\s]+", docstring).group(0)
#
#         web_params = asyncio.run(get_page_content(doc_url))
#
#         self.verify_classes(web_params, CoinbaseAdvancedTradeListFillsRequest)
#
#     def test_get_order(self):
#         docstring = inspect.getdoc(CoinbaseAdvancedTradeGetOrderRequest)
#         doc_url = re.search(r"https?://[^\s]+", docstring).group(0)
#
#         web_params = asyncio.run(get_page_content(doc_url))
#
#         self.verify_classes(web_params, CoinbaseAdvancedTradeGetOrderRequest)
#
#     def test_list_products(self):
#         docstring = inspect.getdoc(CoinbaseAdvancedTradeListProductsRequest)
#         doc_url = re.search(r"https?://[^\s]+", docstring).group(0)
#
#         web_params = asyncio.run(get_page_content(doc_url))
#
#         self.verify_classes(web_params, CoinbaseAdvancedTradeListProductsRequest)
#
#     def test_get_product(self):
#         docstring = inspect.getdoc(CoinbaseAdvancedTradeGetProductRequest)
#         doc_url = re.search(r"https?://[^\s]+", docstring).group(0)
#
#         web_params = asyncio.run(get_page_content(doc_url))
#
#         self.verify_classes(web_params, CoinbaseAdvancedTradeGetProductRequest)
#
#     def test_get_market_trades(self):
#         docstring = inspect.getdoc(CoinbaseAdvancedTradeGetMarketTradesRequest)
#         doc_url = re.search(r"https?://[^\s]+", docstring).group(0)
#
#         web_params = asyncio.run(get_page_content(doc_url))
#
#         self.verify_classes(web_params, CoinbaseAdvancedTradeGetMarketTradesRequest)
#
#     def test_get_product_candles(self):
#         docstring = inspect.getdoc(CoinbaseAdvancedTradeGetProductCandlesRequest)
#         doc_url = re.search(r"https?://[^\s]+", docstring).group(0)
#
#         web_params = asyncio.run(get_page_content(doc_url))
#
#         self.verify_classes(web_params, CoinbaseAdvancedTradeGetProductCandlesRequest)
#
#     def test_get_transaction_summary(self):
#         docstring = inspect.getdoc(CoinbaseAdvancedTradeGetTransactionSummaryRequest)
#         doc_url = re.search(r"https?://[^\s]+", docstring).group(0)
#
#         web_params = asyncio.run(get_page_content(doc_url))
#
#         self.verify_classes(web_params, CoinbaseAdvancedTradeGetTransactionSummaryRequest)
#
#
# if __name__ == "__main__":
#     unittest.main()

# List of classes you want to test
classes_under_test = [CoinbaseAdvancedTradeRequestType.get_registry()[key]
                      for key in CoinbaseAdvancedTradeRequestType.get_registry().keys()
                      if "CreateOrder" not in key]

# classes_under_test = [CoinbaseAdvancedTradeGetTransactionSummaryRequest]
# Dynamically create a subclass for each class you want to test
for class_under_test in classes_under_test:
    name = f"Test{class_under_test.__name__}"
    # globals()[name] = type(name, (ClassValidationWithWebDocumentation.TestSuite,), {"class_under_test": class_under_test})
    globals()[name] = type(name, (ClassValidationFromJsonDocstring.TestSuite,), {"class_under_test": class_under_test})

if __name__ == "__main__":
    unittest.main()
