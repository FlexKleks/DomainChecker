"""
WHOIS Client module for domain availability checking.

This module provides a WHOIS client with strict signal parsing for
determining domain availability. It uses predefined "no match" signals
per TLD without any heuristics.

Requirements: 3.3, 3.4
"""

import asyncio
import socket
from dataclasses import dataclass
from typing import Optional

from .enums import WHOISErrorCode, WHOISStatus



@dataclass
class WHOISError:
    """Error information from a WHOIS query."""

    code: WHOISErrorCode
    message: str


@dataclass
class WHOISResponse:
    """Response from a WHOIS query."""

    status: WHOISStatus
    raw_response: Optional[str]
    no_match_signal_detected: bool
    error: Optional[WHOISError]


class WHOISClient:
    """
    WHOIS client with strict signal parsing.

    This client queries WHOIS servers and uses predefined "no match" signals
    per TLD to determine domain availability. It does NOT use heuristics -
    only exact signal matching is performed.

    Per Requirements 3.3 and 3.4:
    - Uses strict "no match" signal parsing
    - Ambiguous responses result in AMBIGUOUS status (treated as taken)
    """

    # Defined "no match" signals per TLD
    # These are the ONLY signals that indicate a domain is available
    # Any response not containing these exact signals is treated as ambiguous
    NO_MATCH_SIGNALS: dict[str, list[str]] = {
        "de": ["Status: free"],
        "com": ["No match for domain"],
        "net": ["No match for domain"],
        "org": ["NOT FOUND"],
        "eu": ["Status: AVAILABLE"],
        "io": ["NOT FOUND"],
        "co": ["No Data Found"],
        "info": ["NOT FOUND"],
        "biz": ["Not found:"],
    }

    # Default WHOIS servers per TLD
    WHOIS_SERVERS: dict[str, str] = {
        "de": "whois.denic.de",
        "com": "whois.verisign-grs.com",
        "net": "whois.verisign-grs.com",
        "org": "whois.pir.org",
        "eu": "whois.eu",
        "io": "whois.nic.io",
        "co": "whois.nic.co",
        "info": "whois.afilias.net",
        "biz": "whois.biz",
    }

    def __init__(
        self,
        timeout: float = 10.0,
        custom_servers: Optional[dict[str, str]] = None,
        custom_signals: Optional[dict[str, list[str]]] = None,
        simulation_mode: bool = False,
    ) -> None:
        """
        Initialize the WHOIS client.

        Args:
            timeout: Socket timeout in seconds
            custom_servers: Optional custom WHOIS servers per TLD
            custom_signals: Optional custom no-match signals per TLD
            simulation_mode: If True, no real network requests are made
        """
        self._timeout = timeout
        self._simulation_mode = simulation_mode

        # Merge custom servers with defaults
        self._servers = dict(self.WHOIS_SERVERS)
        if custom_servers:
            self._servers.update(custom_servers)

        # Merge custom signals with defaults
        self._signals = dict(self.NO_MATCH_SIGNALS)
        if custom_signals:
            self._signals.update(custom_signals)

    async def query(self, domain: str) -> WHOISResponse:
        """
        Query WHOIS for a domain with strict signal parsing.

        Args:
            domain: The domain to query (should be in canonical form)

        Returns:
            WHOISResponse with status and parsed information

        The response status will be:
        - NOT_FOUND: If an exact "no match" signal is detected
        - FOUND: If the response clearly indicates registration
        - AMBIGUOUS: If the response is unclear (treated as taken per Req 3.4)
        - ERROR: If a network or parsing error occurred
        """
        if self._simulation_mode:
            return self._get_simulated_response(domain)

        tld = self._extract_tld(domain)
        server = self._get_server_for_tld(tld)

        if not server:
            return WHOISResponse(
                status=WHOISStatus.ERROR,
                raw_response=None,
                no_match_signal_detected=False,
                error=WHOISError(
                    code=WHOISErrorCode.NETWORK_ERROR,
                    message=f"No WHOIS server configured for TLD: {tld}",
                ),
            )

        try:
            raw_response = await self._execute_whois_query(domain, server)
            return self._parse_response(raw_response, tld)
        except asyncio.TimeoutError:
            return WHOISResponse(
                status=WHOISStatus.ERROR,
                raw_response=None,
                no_match_signal_detected=False,
                error=WHOISError(
                    code=WHOISErrorCode.TIMEOUT,
                    message=f"WHOIS query timed out after {self._timeout}s",
                ),
            )
        except socket.error as e:
            return WHOISResponse(
                status=WHOISStatus.ERROR,
                raw_response=None,
                no_match_signal_detected=False,
                error=WHOISError(
                    code=WHOISErrorCode.NETWORK_ERROR,
                    message=f"Socket error: {e}",
                ),
            )
        except Exception as e:
            return WHOISResponse(
                status=WHOISStatus.ERROR,
                raw_response=None,
                no_match_signal_detected=False,
                error=WHOISError(
                    code=WHOISErrorCode.PARSE_ERROR,
                    message=f"Unexpected error: {e}",
                ),
            )

    async def _execute_whois_query(self, domain: str, server: str) -> str:
        """
        Execute the actual WHOIS query via socket.

        Args:
            domain: Domain to query
            server: WHOIS server hostname

        Returns:
            Raw WHOIS response as string
        """
        loop = asyncio.get_event_loop()

        def _sync_query() -> str:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(self._timeout)
                sock.connect((server, 43))
                # Send domain query with CRLF
                sock.sendall(f"{domain}\r\n".encode("utf-8"))

                # Receive response
                response_parts: list[bytes] = []
                while True:
                    data = sock.recv(4096)
                    if not data:
                        break
                    response_parts.append(data)

                return b"".join(response_parts).decode("utf-8", errors="replace")

        return await asyncio.wait_for(
            loop.run_in_executor(None, _sync_query),
            timeout=self._timeout,
        )

    def _parse_response(self, raw_response: str, tld: str) -> WHOISResponse:
        """
        Parse WHOIS response with strict signal matching.

        Per Requirement 3.4: Ambiguous signals result in AMBIGUOUS status
        (which is treated as taken by the decision engine).

        Args:
            raw_response: Raw WHOIS response text
            tld: TLD for signal lookup

        Returns:
            WHOISResponse with appropriate status
        """
        if not raw_response or not raw_response.strip():
            # Empty response is ambiguous
            return WHOISResponse(
                status=WHOISStatus.AMBIGUOUS,
                raw_response=raw_response,
                no_match_signal_detected=False,
                error=None,
            )

        # Check for exact "no match" signals
        signals = self._signals.get(tld, [])
        for signal in signals:
            if signal in raw_response:
                return WHOISResponse(
                    status=WHOISStatus.NOT_FOUND,
                    raw_response=raw_response,
                    no_match_signal_detected=True,
                    error=None,
                )

        # Check for common registration indicators
        # These indicate the domain is definitely taken
        registration_indicators = [
            "Domain Name:",
            "Registrant:",
            "Creation Date:",
            "Registry Domain ID:",
            "Registrar:",
            "Name Server:",
            "DNSSEC:",
        ]

        for indicator in registration_indicators:
            if indicator in raw_response:
                return WHOISResponse(
                    status=WHOISStatus.FOUND,
                    raw_response=raw_response,
                    no_match_signal_detected=False,
                    error=None,
                )

        # No clear signal found - response is ambiguous
        # Per Requirement 3.4: Ambiguous responses are treated as taken
        return WHOISResponse(
            status=WHOISStatus.AMBIGUOUS,
            raw_response=raw_response,
            no_match_signal_detected=False,
            error=None,
        )

    def _extract_tld(self, domain: str) -> str:
        """Extract TLD from domain string."""
        parts = domain.lower().split(".")
        return parts[-1] if parts else ""

    def _get_server_for_tld(self, tld: str) -> Optional[str]:
        """Get WHOIS server for a TLD."""
        return self._servers.get(tld.lower())

    def get_supported_tlds(self) -> list[str]:
        """Return list of TLDs with configured WHOIS servers."""
        return list(self._servers.keys())

    def get_signals_for_tld(self, tld: str) -> list[str]:
        """Return the "no match" signals for a specific TLD."""
        return self._signals.get(tld.lower(), [])

    def has_signals_for_tld(self, tld: str) -> bool:
        """Check if signals are defined for a TLD."""
        return tld.lower() in self._signals

    def _get_simulated_response(self, domain: str) -> WHOISResponse:
        """
        Return a simulated response for testing.

        In simulation mode, domains starting with 'available-' are
        returned as NOT_FOUND, others as FOUND.
        """
        tld = self._extract_tld(domain)
        sld = domain.split(".")[0] if "." in domain else domain

        if sld.startswith("available-"):
            signals = self._signals.get(tld, ["NOT FOUND"])
            signal = signals[0] if signals else "NOT FOUND"
            return WHOISResponse(
                status=WHOISStatus.NOT_FOUND,
                raw_response=f"[SIMULATED]\n{signal}\n",
                no_match_signal_detected=True,
                error=None,
            )
        else:
            return WHOISResponse(
                status=WHOISStatus.FOUND,
                raw_response=(
                    "[SIMULATED]\n"
                    f"Domain Name: {domain.upper()}\n"
                    "Registrar: Example Registrar\n"
                    "Creation Date: 2020-01-01\n"
                ),
                no_match_signal_detected=False,
                error=None,
            )
