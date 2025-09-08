"""Authentication and token management."""

import os
from typing import Optional


class AuthManager:
    """Handles authentication and token management."""

    def __init__(self, token_path: str) -> None:
        """Initialize auth manager with token path."""
        self.token_path = token_path

    def load_access_token(self) -> Optional[str]:
        """
        Load access token from file, supporting legacy formats.

        Returns:
            Optional[str]: Access token or None if not found.
        """
        try:
            if not os.path.exists(self.token_path):
                return None
            with open(self.token_path, encoding="utf-8") as f:
                lines = f.read().splitlines()
            if not lines:
                return None

            # Check for legacy formats and clean them up if found
            has_legacy_cache = any(";;" in ln for ln in lines)
            has_legacy_user_id = ":" in lines[0] and lines[0].split(":", 1)[0].isdigit()

            # Cleans up the file and returns the token directly
            if has_legacy_cache or has_legacy_user_id:
                return self.cleanup_legacy_formats(lines, has_legacy_user_id)

            # If no legacy formats, the first line should have the token.
            return lines[0].strip()

        except Exception as e:
            print(f"Error reading access token: {e}")
            return None

    def cleanup_legacy_formats(self, lines: list[str], has_legacy_user_id: bool) -> str:
        """
        Clean legacy cache entries and user_id from token file.

        Args:
            lines (list[str]): Lines read from token file.
            has_legacy_user_id (bool): Whether first line has user_id:token format.

        Returns:
            str: Cleaned token.
        """
        token = ""
        try:
            header = lines[0] if lines else ""

            # Extract just the token if it's in user_id:token format
            token = header.split(":", 1)[1].strip() if has_legacy_user_id and ":" in header else header.strip()

            # Rewrite token file with just the token, removing user_id and cache lines
            with open(self.token_path, "w", encoding="utf-8") as f:
                f.write(token + ("\n" if token else ""))

            if has_legacy_user_id:
                print("Cleaned up legacy user_id from token file.")
            if any(";;" in ln for ln in lines):
                print("Cleaned up legacy cache entries from token file.")
        except Exception as e:
            print(f"Legacy format cleanup failed: {e}")

        return token
