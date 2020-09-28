import time
import hmac
import hashlib
import base64
from typing import Dict
import re

from wsgiref.handlers import format_date_time
from datetime import datetime
from time import mktime


class EterbaseAuth():
    """
    Auth class required by Eterbase API
    """

    _UTF8 = 'utf-8'
    _HTTP_METHOD_GET = "GET"
    _HTTP_METHOD_DELETE = "DELETE"
    _HMAC_SHA256 = "hmac-sha256"
    _HEADER_DATE = "Date"
    _HEADER_AUTHORIZATION = "Authorization"
    _HEADER_DIGEST = "Digest"

    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key

    def generate_auth_dict(self, method: str, path_url: str, body: str = None) -> Dict[str, any]:
        """
        Generates authentication signature and return it in a dictionary along with other inputs
        :return: a dictionary of request info including the request signature
        """
        timestamp = str(time.time())
        message = timestamp + method.upper() + path_url + body
        hmac_key = base64.b64decode(self.secret_key)
        signature = hmac.new(hmac_key, message.encode(EterbaseAuth._UTF8), hashlib.sha256)
        signature_b64 = base64.b64encode(bytes(signature.digest())).decode(EterbaseAuth._UTF8)

        return {
            "signature": signature_b64,
            "timestamp": timestamp,
            "key": self.api_key
        }

    def get_headers(self, method: str, path_url: str, body: str = None) -> Dict[str, any]:
        """
        Generates authentication headers required by eterbase
        :param method: GET / POST / etc.
        :param path_url: e.g. "/accounts"
        :param body: request payload
        :return: a dictionary of auth headers
        """
        header_dict = self.gen_auth_dict_eter(method, path_url, body)
        return header_dict

    def gen_auth_dict_eter(self, method: str, path_url: str, body: str = None):
        # Set the authorization header template
        auth_header_template = (
            'hmac username="{}",algorithm="{}",headers="{}",signature="{}"'
        )

        # Set the date header
        date_header = self.get_date_header()
        # Set headers for the signature hash
        signature_headers = {"date": date_header}

        if (body is not None):
            base64sha256 = "SHA-256=" + self.sha256_hash_base64(body)
            signature_headers["digest"] = base64sha256

        # Strip the hostname from the URL
        target_url = re.sub(r"^https?://[^/]+/", "/", path_url)
        # Build the request-line header
        request_line = method.upper() + " " + target_url + " HTTP/1.1"
        # Add to headers for the signature hash
        signature_headers["request-line"] = request_line

        # Get the list of headers
        headers = self.get_headers_string(signature_headers)
        # Build the signature string
        signature_string = self.get_signature_string(signature_headers)
        # Hash the signature string using the specified algorithm
        signature_hash = self.sha256_hash_base64(signature_string, self.secret_key)
        # Format the authorization header
        auth_header = auth_header_template.format(
            self.api_key, EterbaseAuth._HMAC_SHA256, headers, (signature_hash).decode(EterbaseAuth._UTF8)
        )

        request_headers = None
        if (method.upper() == EterbaseAuth._HTTP_METHOD_GET) or (method.upper() == EterbaseAuth._HTTP_METHOD_DELETE):
            request_headers = {
                EterbaseAuth._HEADER_AUTHORIZATION: auth_header,
                EterbaseAuth._HEADER_DATE: date_header
            }
        else:
            request_headers = {
                EterbaseAuth._HEADER_AUTHORIZATION: auth_header,
                EterbaseAuth._HEADER_DATE: date_header,
                EterbaseAuth._HEADER_DIGEST: base64sha256
            }

        return request_headers

    def get_date_header(self):
        now = datetime.now()
        stamp = mktime(now.timetuple())
        return format_date_time(stamp)

    def sha256_hash_base64(self, string_to_hash, secret = None):
        if secret is None:
            m = hashlib.sha256()
            m.update(string_to_hash.encode(EterbaseAuth._UTF8))
            return base64.b64encode(m.digest()).decode(EterbaseAuth._UTF8)
        else:
            h = hmac.new((secret).encode(EterbaseAuth._UTF8), (string_to_hash).encode(EterbaseAuth._UTF8), hashlib.sha256)
            return base64.b64encode(h.digest())

    def get_signature_string(self, signature_headers):
        sig_string = ""
        for key, value in signature_headers.items():
            if sig_string != "":
                sig_string += "\n"
            if key.lower() == "request-line":
                sig_string += value
            else:
                sig_string += key.lower() + ": " + value
        return sig_string

    def get_headers_string(self, signature_headers):
        headers = ""
        for key in signature_headers:
            if headers != "":
                headers += " "
            headers += key
        return headers
