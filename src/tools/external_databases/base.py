"""Base class for external database lookup tools.

This module provides a reusable base class that implements common patterns
for querying external biochemical and molecular biology databases:
- HTTP session management with retry logic
- Async/await pattern for non-blocking queries
- Standardized error handling and result formatting
- Configurable timeouts and rate limiting
- Request/response logging
"""

import logging
from typing import Any, Dict, Optional
from abc import ABC, abstractmethod

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from src.tools.base import BaseTool, ToolResult, ToolStatus

logger = logging.getLogger(__name__)


class BaseDatabaseLookupTool(BaseTool, ABC):
    """Base class for external database lookup tools.

    This class provides common functionality for all database lookup tools:
    - HTTP session management with automatic retry logic
    - Configurable timeouts and retry strategies
    - Standardized error handling
    - Request/response logging

    Child classes only need to implement:
    - execute(): The main query logic
    - Optional: parse_response(): Response parsing logic

    Example:
        class MyDatabaseTool(BaseDatabaseLookupTool):
            TOOL_NAME = "my_database"
            BASE_URL = "https://api.example.com"

            async def execute(self, query: str) -> ToolResult:
                url = f"{self.BASE_URL}/search?q={query}"
                response = await self._make_request(url)
                data = self._parse_json_response(response)
                return ToolResult.success(data=data)
    """

    # Subclasses should define these
    TOOL_NAME: str = None  # Tool identifier
    BASE_URL: str = None  # Database base URL

    # Default configuration (can be overridden)
    DEFAULT_TIMEOUT = 10
    MAX_RETRIES = 3
    RETRY_BACKOFF = 0.5
    RATE_LIMIT_DELAY = 0.0  # Seconds to wait between requests

    # HTTP status codes to retry
    RETRY_STATUS_CODES = [429, 500, 502, 503, 504]

    # Default headers
    DEFAULT_HEADERS = {
        "User-Agent": "GPTase-Framework/1.0 (https://github.com/l1zp/GPTase)",
        "Accept": "application/json",
    }

    def __init__(self, base_url: Optional[str] = None):
        """Initialize database lookup tool.

        Args:
            base_url: Override the default BASE_URL
        """
        if base_url:
            self.BASE_URL = base_url

        super().__init__(
            name=self.TOOL_NAME,
            description=f"Look up data from {self.TOOL_NAME.replace('_', ' ').title()}",
        )

        self._session = self._create_session()
        self._last_request_time = 0.0

    def _create_session(self) -> requests.Session:
        """Create HTTP session with retry logic.

        Returns:
            Configured requests.Session with retry adapter
        """
        session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=self.MAX_RETRIES,
            backoff_factor=self.RETRY_BACKOFF,
            status_forcelist=self.RETRY_STATUS_CODES,
            allowed_methods=["GET", "POST"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        # Set default headers
        session.headers.update(self.DEFAULT_HEADERS)

        return session

    async def _make_request(
        self,
        url: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> requests.Response:
        """Make HTTP request with rate limiting and error handling.

        Args:
            url: Request URL
            method: HTTP method (GET, POST, etc.)
            params: Query parameters
            data: Request body data
            headers: Additional headers (merged with DEFAULT_HEADERS)
            timeout: Request timeout (uses DEFAULT_TIMEOUT if None)

        Returns:
            Response object

        Raises:
            requests.HTTPError: If request fails after retries
        """
        import time

        # Rate limiting
        if self.RATE_LIMIT_DELAY > 0:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.RATE_LIMIT_DELAY:
                wait_time = self.RATE_LIMIT_DELAY - elapsed
                logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
                time.sleep(wait_time)

        # Prepare headers
        request_headers = self.DEFAULT_HEADERS.copy()
        if headers:
            request_headers.update(headers)

        # Make request
        timeout = timeout or self.DEFAULT_TIMEOUT

        logger.debug(f"Making {method} request to {url}")

        try:
            response = self._session.request(
                method=method,
                url=url,
                params=params,
                data=data,
                headers=request_headers,
                timeout=timeout,
            )
            response.raise_for_status()

            self._last_request_time = time.time()
            return response

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error on {url}: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error on {url}: {e}")
            raise

    def _parse_json_response(self, response: requests.Response) -> Dict[str, Any]:
        """Parse JSON response.

        Args:
            response: HTTP response object

        Returns:
            Parsed JSON data

        Raises:
            ValueError: If response is not valid JSON
        """
        try:
            return response.json()
        except ValueError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            raise

    def _parse_tsv_response(
        self, response: requests.Response
    ) -> list[list[str]]:
        """Parse TSV (tab-separated values) response.

        Args:
            response: HTTP response object

        Returns:
            List of rows (each row is a list of string values)
        """
        lines = response.text.strip().split("\n")
        return [line.split("\t") for line in lines]

    @abstractmethod
    async def execute(self, *args, **kwargs) -> ToolResult:
        """Execute database lookup.

        This method must be implemented by subclasses.

        Returns:
            ToolResult with lookup results
        """
        pass

    async def close(self):
        """Close HTTP session and cleanup resources."""
        if self._session:
            self._session.close()
            self._session = None
            logger.debug(f"Closed {self.TOOL_NAME} database session")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    def __enter__(self):
        """Sync context manager entry (for backward compatibility)."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Sync context manager exit."""
        self.close()


class BaseAPITool(BaseDatabaseLookupTool):
    """Base class for REST API database tools.

    This extends BaseDatabaseLookupTool with additional convenience
    methods for REST API interactions.

    Example:
        class MyAPITool(BaseAPITool):
            TOOL_NAME = "my_api"
            BASE_URL = "https://api.example.com/v1"

            async def execute(self, query: str) -> ToolResult:
                endpoint = f"{self.BASE_URL}/search"
                data = await self._api_get(endpoint, params={"q": query})
                return ToolResult.success(data=data)
    """

    async def _api_get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make GET request to API endpoint.

        Args:
            endpoint: API endpoint path (will be appended to BASE_URL)
            params: Query parameters
            headers: Additional headers

        Returns:
            Parsed JSON response
        """
        url = endpoint if endpoint.startswith("http") else f"{self.BASE_URL}/{endpoint}"
        response = await self._make_request(url, method="GET", params=params, headers=headers)
        return self._parse_json_response(response)

    async def _api_post(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make POST request to API endpoint.

        Args:
            endpoint: API endpoint path
            data: Form data
            json: JSON data
            headers: Additional headers

        Returns:
            Parsed JSON response
        """
        url = endpoint if endpoint.startswith("http") else f"{self.BASE_URL}/{endpoint}"

        if json:
            response = await self._make_request(
                url, method="POST", data=data, json=json, headers=headers
            )
        else:
            response = await self._make_request(url, method="POST", data=data, headers=headers)

        return self._parse_json_response(response)


class BaseHTMLTool(BaseDatabaseLookupTool):
    """Base class for HTML scraping tools.

    This extends BaseDatabaseLookupTool for databases that don't provide
    a REST API and require HTML parsing.

    Example:
        class MyHTMLTool(BaseHTMLTool):
            TOOL_NAME = "my_html_db"
            BASE_URL = "https://example.com/database"

            async def execute(self, query: str) -> ToolResult:
                url = f"{self.BASE_URL}/search?q={query}"
                soup = await self._get_html_soup(url)
                # Parse HTML and extract data
                return ToolResult.success(data=extracted_data)
    """

    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    async def _get_html_soup(self, url: str) -> "BeautifulSoup":
        """Get BeautifulSoup object from HTML page.

        Args:
            url: URL to fetch

        Returns:
            BeautifulSoup object for parsing HTML

        Raises:
            ImportError: If BeautifulSoup is not installed
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            raise ImportError(
                "BeautifulSoup4 is required for HTML parsing. "
                "Install it with: pip install beautifulsoup4"
            )

        response = await self._make_request(url)
        return BeautifulSoup(response.text, "html.parser")

    def _extract_text(self, element) -> str:
        """Extract and clean text from HTML element.

        Args:
            element: BeautifulSoup element

        Returns:
            Cleaned text content
        """
        if element is None:
            return ""
        return element.get_text(strip=True)
