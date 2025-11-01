"""API communication logic for AniList GraphQL API."""

import sys
from typing import Any, Optional

import requests


class APIClient:
    """Handles communication with AniList GraphQL API."""

    ANILIST_API_URL: str = "https://graphql.anilist.co"

    def make_api_request(
        self, query: str, variables: Optional[dict[str, Any]] = None, access_token: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        """
        Make POST request to AniList GraphQL API.

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

        try:
            response = requests.post(
                self.ANILIST_API_URL, json={"query": query, "variables": variables}, headers=headers, timeout=10
            )
            if response.status_code == 200:
                return response.json()
            print(
                f"API request failed: {response.status_code} - {response.text}\nQuery: {query}\nVariables: {variables}",
                file=sys.stderr,
            )
            return None
        except requests.exceptions.RequestException as e:
            print(f"Network error connecting to AniList API: {e}", file=sys.stderr)
            return None
