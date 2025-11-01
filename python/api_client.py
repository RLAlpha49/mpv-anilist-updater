"""API communication logic for AniList GraphQL API."""

import sys
import time
from typing import Any, Optional

import requests


class APIClient:
    """Handles communication with AniList GraphQL API."""

    ANILIST_API_URL: str = "https://graphql.anilist.co"
    MAX_RETRIES: int = 2
    RETRY_BACKOFF_MS: int = 250

    def make_api_request(
        self, query: str, variables: Optional[dict[str, Any]] = None, access_token: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        """
        Make POST request to AniList GraphQL API with retry logic.

        Args:
            query (str): GraphQL query string.
            variables (Optional[dict[str, Any]]): Query variables.
            access_token (Optional[str]): AniList access token.

        Returns:
            Optional[dict[str, Any]]: API response or None on error.
        """
        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                response = requests.post(
                    self.ANILIST_API_URL,
                    json={"query": query, "variables": variables},
                    headers=headers,
                    timeout=10,
                )
                if response.status_code == 200:
                    return response.json()

                # Only retry on 5xx server errors
                if response.status_code >= 500 and attempt < self.MAX_RETRIES:
                    time.sleep(self.RETRY_BACKOFF_MS / 1000.0)
                    continue

                # Non-retryable error or final attempt
                print(
                    f"API request failed: {response.status_code} - {response.text}\nQuery: {query}\nVariables: {variables}",
                    file=sys.stderr,
                )
                return None

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                # Retry on timeout and connection errors
                if attempt < self.MAX_RETRIES:
                    time.sleep(self.RETRY_BACKOFF_MS / 1000.0)
                    continue

                # Final attempt failed
                print(f"Network error connecting to AniList API: {e}", file=sys.stderr)
                return None

            except requests.exceptions.RequestException as e:
                # Non-retryable network errors
                print(f"Network error connecting to AniList API: {e}", file=sys.stderr)
                return None

        return None
