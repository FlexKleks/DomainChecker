"""
RDAP Client for domain availability checking.

This module provides an async RDAP client with TLS enforcement,
response parsing for defined fields only, and proper error handling.

Requirements covered:
- 2.1: Query official RDAP endpoint of the respective registry
- 2.2: HTTP 404 with defined "not found" response → potentially available
- 2.3: Valid domain object → taken
- 2.4: Ignore undefined fields, parse only defined RDAP fields
- 2.5: Reject non-TLS connections
"""

from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import quote, urlparse, urlunparse
import json
import time

import httpx

from .enums import RDAPErrorCode, RDAPStatus
from .exceptions import NetworkError


@dataclass
class RDAPEvent:
    """A single RDAP event (e.g., registration, expiration)."""

    event_action: str
    event_date: str


@dataclass
class RDAPParsedFields:
    """
    Parsed RDAP response fields.

    Only defined fields are extracted; all others are ignored per Requirement 2.4.
    """

    domain_name: str
    status: list[str]
    events: list[RDAPEvent]
    nameservers: list[str]


@dataclass
class RDAPError:
    """Error information from an RDAP query."""

    code: RDAPErrorCode
    message: str
    http_status_code: Optional[int] = None


@dataclass
class RDAPResponse:
    """Complete RDAP query response."""

    status: RDAPStatus
    http_status_code: int
    raw_response: Optional[Any]
    parsed_fields: Optional[RDAPParsedFields]
    error: Optional[RDAPError]
    response_time_ms: float = 0.0



class RDAPClient:
    """
    Async RDAP client with TLS enforcement.

    This client queries RDAP endpoints for domain availability information,
    enforcing TLS connections and parsing only defined response fields.
    """

    # Defined "not found" indicators in RDAP 404 responses
    NOT_FOUND_INDICATORS = [
        "not found",
        "no match",
        "object does not exist",
        "domain not found",
    ]

    # Path segment RDAP uses for domain lookups (RFC 7482, Section 3.1.3)
    DOMAIN_PATH_SEGMENT = "domain"

    def __init__(
        self,
        tld_endpoints: dict[str, str],
        timeout: float = 10.0,
        simulation_mode: bool = False,
    ) -> None:
        """
        Initialize the RDAP client.

        Args:
            tld_endpoints: Mapping of TLD to RDAP endpoint URL
            timeout: Request timeout in seconds
            simulation_mode: If True, no real network requests are made
        """
        self._tld_endpoints = {k.lower(): v for k, v in tld_endpoints.items()}
        self._timeout = timeout
        self._simulation_mode = simulation_mode
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "RDAPClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            verify=True,  # TLS certificate verification enforced
            timeout=httpx.Timeout(self._timeout),
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def get_endpoint_for_tld(self, tld: str) -> Optional[str]:
        """
        Get the RDAP endpoint URL for a given TLD.

        Args:
            tld: The top-level domain (e.g., 'com', 'de')

        Returns:
            The RDAP endpoint URL or None if not configured
        """
        return self._tld_endpoints.get(tld.lower())

    def _validate_endpoint_url(self, endpoint: str) -> None:
        """
        Validate that the endpoint uses HTTPS (TLS).

        Requirement 2.5: Non-TLS connections must be rejected.

        Args:
            endpoint: The endpoint URL to validate

        Raises:
            NetworkError: If the endpoint does not use HTTPS
        """
        parsed = urlparse(endpoint)
        if parsed.scheme.lower() != "https":
            raise NetworkError(
                code=RDAPErrorCode.TLS_ERROR.value,
                message=f"RDAP endpoint must use HTTPS: {endpoint}",
                details={"endpoint": endpoint, "scheme": parsed.scheme},
            )

    @classmethod
    def _build_query_url(cls, endpoint: str, domain: str) -> str:
        """
        Build the RDAP domain lookup URL for a configured endpoint.

        Endpoints are configured inconsistently: most already contain the
        RDAP ``/domain`` path segment (e.g.
        ``https://rdap.verisign.com/com/v1/domain/``), while others only point
        at the RDAP base URL. Appending ``/domain`` unconditionally produced
        invalid URLs such as ``.../com/v1/domain/domain/google.com``, which
        registries answer with HTTP 400.

        The segment is therefore only appended when the endpoint does not
        already end with it.

        Args:
            endpoint: Configured RDAP endpoint URL
            domain: Canonical domain name to look up

        Returns:
            The full RDAP domain lookup URL
        """
        parsed = urlparse(endpoint)
        path = parsed.path.rstrip("/")

        segments = [segment for segment in path.split("/") if segment]
        if not segments or segments[-1].lower() != cls.DOMAIN_PATH_SEGMENT:
            path = f"{path}/{cls.DOMAIN_PATH_SEGMENT}"

        lookup_path = f"{path}/{quote(domain, safe='')}"
        return urlunparse(parsed._replace(path=lookup_path))

    def _parse_response(self, json_data: dict) -> Optional[RDAPParsedFields]:
        """
        Parse RDAP response, extracting only defined fields.

        Requirement 2.4: Ignore undefined fields, parse only defined RDAP fields.

        Args:
            json_data: The raw JSON response from RDAP

        Returns:
            Parsed fields or None if parsing fails
        """
        try:
            # Extract domain name (ldhName or unicodeName)
            domain_name = json_data.get("ldhName") or json_data.get("unicodeName", "")

            # Extract status array
            status = json_data.get("status", [])
            if not isinstance(status, list):
                status = [status] if status else []

            # Extract events
            events = []
            raw_events = json_data.get("events", [])
            if isinstance(raw_events, list):
                for event in raw_events:
                    if isinstance(event, dict):
                        event_action = event.get("eventAction", "")
                        event_date = event.get("eventDate", "")
                        if event_action and event_date:
                            events.append(RDAPEvent(
                                event_action=event_action,
                                event_date=event_date,
                            ))

            # Extract nameservers
            nameservers = []
            raw_nameservers = json_data.get("nameservers", [])
            if isinstance(raw_nameservers, list):
                for ns in raw_nameservers:
                    if isinstance(ns, dict):
                        ns_name = ns.get("ldhName") or ns.get("unicodeName", "")
                        if ns_name:
                            nameservers.append(ns_name)

            return RDAPParsedFields(
                domain_name=domain_name,
                status=status,
                events=events,
                nameservers=nameservers,
            )
        except Exception:
            return None

    @staticmethod
    def _extract_rdap_error_code(body: str) -> Optional[int]:
        """
        Extract the ``errorCode`` from an RDAP error response body.

        Args:
            body: The raw response body

        Returns:
            The numeric ``errorCode``, or None if the body is not an RDAP
            error object carrying a numeric ``errorCode``.
        """
        try:
            data = json.loads(body)
        except Exception:
            return None

        if not isinstance(data, dict):
            return None

        raw_code = data.get("errorCode")
        if raw_code is None or isinstance(raw_code, bool):
            return None

        try:
            return int(raw_code)
        except (TypeError, ValueError):
            return None

    def _is_not_found_response(self, response: httpx.Response) -> bool:
        """
        Check if a 404 response indicates domain not found.

        Requirement 2.2: HTTP 404 with defined "not found" response
        should map to potentially available.

        RFC 7480 Section 5.3 defines HTTP 404 as the response for an object
        that does not exist, and the accompanying RDAP error body is optional.
        Registries such as Verisign answer with a 404 and an empty body, so
        the status code itself is the defined signal. Requiring a textual
        marker in the body classified those responses as errors, which the
        decision engine then reported as "taken".

        A 404 is only rejected when the body carries an RDAP error object
        whose ``errorCode`` contradicts the HTTP status code.

        Args:
            response: The HTTP response to check

        Returns:
            True if this is a valid "not found" response
        """
        if response.status_code != 404:
            return False

        try:
            body = response.text or ""
        except Exception:
            # If we can't read the body, the 404 status code still stands
            return True

        body = body.strip()
        if not body:
            # Empty body: HTTP 404 is the defined "not found" signal
            return True

        lowered = body.lower()
        if any(indicator in lowered for indicator in self.NOT_FOUND_INDICATORS):
            return True

        # An RDAP error object in the body must agree with the HTTP status
        error_code = self._extract_rdap_error_code(body)
        if error_code is not None:
            return error_code == 404

        # No contradicting error object -> the 404 status code is authoritative
        return True

    def _is_valid_domain_object(self, json_data: dict) -> bool:
        """
        Check if the response contains a valid domain object.

        Requirement 2.3: Valid domain object should map to taken.

        Args:
            json_data: The parsed JSON response

        Returns:
            True if this is a valid domain object
        """
        # A valid domain object must have at least domainName/ldhName and status
        has_name = bool(json_data.get("ldhName") or json_data.get("unicodeName"))
        has_status = bool(json_data.get("status"))
        return has_name and has_status


    async def query(self, domain: str, endpoint: Optional[str] = None) -> RDAPResponse:
        """
        Query RDAP for domain information.

        Requirement 2.1: Query the official RDAP endpoint of the respective registry.

        Args:
            domain: The domain to query (should be in canonical form)
            endpoint: Optional specific endpoint URL; if not provided,
                     will be looked up based on TLD

        Returns:
            RDAPResponse with query results

        Raises:
            NetworkError: If TLS validation fails or network error occurs
        """
        start_time = time.perf_counter()

        # Determine endpoint
        if endpoint is None:
            tld = domain.rsplit(".", 1)[-1].lower() if "." in domain else ""
            endpoint = self.get_endpoint_for_tld(tld)
            if endpoint is None:
                return RDAPResponse(
                    status=RDAPStatus.ERROR,
                    http_status_code=0,
                    raw_response=None,
                    parsed_fields=None,
                    error=RDAPError(
                        code=RDAPErrorCode.NETWORK_ERROR,
                        message=f"No RDAP endpoint configured for TLD: {tld}",
                    ),
                    response_time_ms=self._elapsed_ms(start_time),
                )

        # Validate TLS requirement (Requirement 2.5)
        try:
            self._validate_endpoint_url(endpoint)
        except NetworkError as e:
            return RDAPResponse(
                status=RDAPStatus.ERROR,
                http_status_code=0,
                raw_response=None,
                parsed_fields=None,
                error=RDAPError(
                    code=RDAPErrorCode.TLS_ERROR,
                    message=e.message,
                ),
                response_time_ms=self._elapsed_ms(start_time),
            )

        # Simulation mode - return mock response
        if self._simulation_mode:
            return self._create_simulation_response(domain, start_time)

        # Ensure client is initialized
        if self._client is None:
            self._client = httpx.AsyncClient(
                verify=True,
                timeout=httpx.Timeout(self._timeout),
                follow_redirects=True,
            )

        # Build RDAP URL
        rdap_url = self._build_query_url(endpoint, domain)

        try:
            response = await self._client.get(
                rdap_url,
                headers={"Accept": "application/rdap+json, application/json"},
            )

            response_time_ms = self._elapsed_ms(start_time)

            # Handle 404 - potentially available (Requirement 2.2)
            if response.status_code == 404:
                if self._is_not_found_response(response):
                    return RDAPResponse(
                        status=RDAPStatus.NOT_FOUND,
                        http_status_code=404,
                        raw_response=None,
                        parsed_fields=None,
                        error=None,
                        response_time_ms=response_time_ms,
                    )

                # A 404 carrying a contradicting RDAP error object is not a
                # usable "not found" signal. Report it as a parse error so the
                # decision engine stays conservative, and do not retry it:
                # retrying previously turned every unclassified 404 into four
                # identical requests against the registry.
                return RDAPResponse(
                    status=RDAPStatus.ERROR,
                    http_status_code=404,
                    raw_response=None,
                    parsed_fields=None,
                    error=RDAPError(
                        code=RDAPErrorCode.PARSE_ERROR,
                        message=(
                            "HTTP 404 response is not a valid RDAP "
                            "'not found' response"
                        ),
                        http_status_code=404,
                    ),
                    response_time_ms=response_time_ms,
                )

            # Handle rate limiting
            if response.status_code == 429:
                return RDAPResponse(
                    status=RDAPStatus.ERROR,
                    http_status_code=429,
                    raw_response=None,
                    parsed_fields=None,
                    error=RDAPError(
                        code=RDAPErrorCode.RATE_LIMITED,
                        message="Rate limited by RDAP server",
                        http_status_code=429,
                    ),
                    response_time_ms=response_time_ms,
                )

            # Handle server errors
            if response.status_code >= 500:
                return RDAPResponse(
                    status=RDAPStatus.ERROR,
                    http_status_code=response.status_code,
                    raw_response=None,
                    parsed_fields=None,
                    error=RDAPError(
                        code=RDAPErrorCode.SERVER_ERROR,
                        message=f"RDAP server error: {response.status_code}",
                        http_status_code=response.status_code,
                    ),
                    response_time_ms=response_time_ms,
                )

            # Handle successful response (Requirement 2.3)
            if response.status_code == 200:
                try:
                    json_data = response.json()

                    # Check if it's a valid domain object
                    if self._is_valid_domain_object(json_data):
                        parsed = self._parse_response(json_data)
                        return RDAPResponse(
                            status=RDAPStatus.FOUND,
                            http_status_code=200,
                            raw_response=json_data,
                            parsed_fields=parsed,
                            error=None,
                            response_time_ms=response_time_ms,
                        )
                    else:
                        # Response doesn't contain valid domain object
                        return RDAPResponse(
                            status=RDAPStatus.ERROR,
                            http_status_code=200,
                            raw_response=json_data,
                            parsed_fields=None,
                            error=RDAPError(
                                code=RDAPErrorCode.PARSE_ERROR,
                                message="Response does not contain valid domain object",
                                http_status_code=200,
                            ),
                            response_time_ms=response_time_ms,
                        )
                except Exception as e:
                    return RDAPResponse(
                        status=RDAPStatus.ERROR,
                        http_status_code=200,
                        raw_response=None,
                        parsed_fields=None,
                        error=RDAPError(
                            code=RDAPErrorCode.PARSE_ERROR,
                            message=f"Failed to parse RDAP response: {e}",
                            http_status_code=200,
                        ),
                        response_time_ms=response_time_ms,
                    )

            # Handle other status codes as errors
            return RDAPResponse(
                status=RDAPStatus.ERROR,
                http_status_code=response.status_code,
                raw_response=None,
                parsed_fields=None,
                error=RDAPError(
                    code=RDAPErrorCode.SERVER_ERROR,
                    message=f"Unexpected HTTP status: {response.status_code}",
                    http_status_code=response.status_code,
                ),
                response_time_ms=response_time_ms,
            )

        except httpx.TimeoutException:
            return RDAPResponse(
                status=RDAPStatus.ERROR,
                http_status_code=0,
                raw_response=None,
                parsed_fields=None,
                error=RDAPError(
                    code=RDAPErrorCode.TIMEOUT,
                    message=f"RDAP request timed out after {self._timeout}s",
                ),
                response_time_ms=self._elapsed_ms(start_time),
            )
        except httpx.ConnectError as e:
            error_msg = str(e)
            # Check for TLS/SSL errors
            if "ssl" in error_msg.lower() or "certificate" in error_msg.lower():
                return RDAPResponse(
                    status=RDAPStatus.ERROR,
                    http_status_code=0,
                    raw_response=None,
                    parsed_fields=None,
                    error=RDAPError(
                        code=RDAPErrorCode.TLS_ERROR,
                        message=f"TLS connection error: {error_msg}",
                    ),
                    response_time_ms=self._elapsed_ms(start_time),
                )
            return RDAPResponse(
                status=RDAPStatus.ERROR,
                http_status_code=0,
                raw_response=None,
                parsed_fields=None,
                error=RDAPError(
                    code=RDAPErrorCode.NETWORK_ERROR,
                    message=f"Connection error: {error_msg}",
                ),
                response_time_ms=self._elapsed_ms(start_time),
            )
        except Exception as e:
            return RDAPResponse(
                status=RDAPStatus.ERROR,
                http_status_code=0,
                raw_response=None,
                parsed_fields=None,
                error=RDAPError(
                    code=RDAPErrorCode.NETWORK_ERROR,
                    message=f"Unexpected error: {e}",
                ),
                response_time_ms=self._elapsed_ms(start_time),
            )

    def _elapsed_ms(self, start_time: float) -> float:
        """Calculate elapsed time in milliseconds."""
        return (time.perf_counter() - start_time) * 1000

    def _create_simulation_response(
        self, domain: str, start_time: float
    ) -> RDAPResponse:
        """Create a simulated response for testing without network access."""
        # In simulation mode, return a "found" response to be conservative
        return RDAPResponse(
            status=RDAPStatus.FOUND,
            http_status_code=200,
            raw_response={"ldhName": domain, "status": ["active"]},
            parsed_fields=RDAPParsedFields(
                domain_name=domain,
                status=["active"],
                events=[],
                nameservers=[],
            ),
            error=None,
            response_time_ms=self._elapsed_ms(start_time),
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
