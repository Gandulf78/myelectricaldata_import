"""Request."""

import logging
from typing import Optional, Dict, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config.main import APP_CONFIG


class Query(object):
    """Requests object with retry logic."""

    def __init__(self, endpoint: str, headers: Optional[Dict[str, str]] = None):
        self.endpoint = endpoint
        self.timeout = 120  # Increased default timeout to 120 seconds
        if not headers:
            self.headers = {"Content-Type": "application/x-www-form-urlencoded"}
        else:
            self.headers = headers

        # Configure retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,  # number of retries
            backoff_factor=1,  # wait 1, 2, 4 seconds between retries
            status_forcelist=[500, 502, 503, 504],  # HTTP status codes to retry on
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def get(self, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        """Get with retry logic."""
        logging.debug(f"[GET] Endpoint {self.endpoint}")
        logging.debug(f" - url : {self.endpoint}")
        logging.debug(f" - headers : {self.headers}")
        logging.debug(f" - params : {params}")
        response = {}
        try:
            response = self.session.get(
                url=self.endpoint,
                headers=self.headers,
                params=params,
                timeout=self.timeout,
                verify=APP_CONFIG.gateway.ssl,
            )
            logging.debug(f"[RESPONSE] : status_code {response.status_code}")
            logging.debug(f" => {response.text}...")
        except requests.exceptions.Timeout as e:
            logging.error(f"Request timed out after {self.timeout} seconds: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logging.error(f"Request failed: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            raise
        return response

    def post(self, params: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None) -> requests.Response:
        """Post with retry logic."""
        logging.debug(f"[POST] Endpoint {self.endpoint}")
        logging.debug(f" - url : {self.endpoint}")
        logging.debug(f" - headers : {self.headers}")
        logging.debug(f" - params : {params}")
        logging.debug(f" - data : {data}")
        response = {}
        try:
            response = self.session.post(
                url=self.endpoint,
                headers=self.headers,
                params=params,
                data=data,
                timeout=self.timeout,
                verify=APP_CONFIG.gateway.ssl,
            )
            logging.debug(f"[RESPONSE] : status_code {response.status_code}")
            logging.debug(f" => {response.text}...")
        except requests.exceptions.Timeout as e:
            logging.error(f"Request timed out after {self.timeout} seconds: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logging.error(f"Request failed: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            raise
        return response

    def delete(self, params: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None) -> requests.Response:
        """Delete with retry logic."""
        logging.debug(f"[DELETE] Endpoint {self.endpoint}")
        logging.debug(f" - headers : {self.headers}")
        logging.debug(f" - params : {params}")
        logging.debug(f" - data : {data}")
        response = {}
        try:
            response = self.session.delete(
                url=self.endpoint,
                headers=self.headers,
                params=params,
                data=data,
                timeout=self.timeout,
                verify=APP_CONFIG.gateway.ssl,
            )
            logging.debug(f"[RESPONSE] : status_code {response.status_code}")
            logging.debug(f" => {response.text}...")
        except requests.exceptions.Timeout as e:
            logging.error(f"Request timed out after {self.timeout} seconds: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logging.error(f"Request failed: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            raise
        return response

    def update(self, params: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None) -> requests.Response:
        """Update with retry logic."""
        logging.debug(f"[UPDATE] Endpoint {self.endpoint}")
        logging.debug(f" - headers : {self.headers}")
        logging.debug(f" - params : {params}")
        logging.debug(f" - data : {data}")
        response = {}
        try:
            response = self.session.request(
                "UPDATE",
                url=self.endpoint,
                headers=self.headers,
                params=params,
                data=data,
                timeout=self.timeout,
                verify=APP_CONFIG.gateway.ssl,
            )
            logging.debug(f"[RESPONSE] : status_code {response.status_code}")
            logging.debug(f" => {response.text}...")
        except requests.exceptions.Timeout as e:
            logging.error(f"Request timed out after {self.timeout} seconds: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logging.error(f"Request failed: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            raise
        return response

    def put(self, params: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None) -> requests.Response:
        """Put with retry logic."""
        logging.debug(f"[PUT] Endpoint {self.endpoint}")
        logging.debug(f" - headers : {self.headers}")
        logging.debug(f" - params : {params}")
        logging.debug(f" - data : {data}")
        response = {}
        try:
            response = self.session.put(
                url=self.endpoint,
                headers=self.headers,
                params=params,
                data=data,
                timeout=self.timeout,
                verify=APP_CONFIG.gateway.ssl,
            )
            logging.debug(f"[RESPONSE] : status_code {response.status_code}")
            logging.debug(f" => {response.text}...")
        except requests.exceptions.Timeout as e:
            logging.error(f"Request timed out after {self.timeout} seconds: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logging.error(f"Request failed: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            raise
        return response
