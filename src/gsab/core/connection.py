from typing import Optional, Sequence

from googleapiclient.discovery import build

from ..auth.resolver import DEFAULT_SCOPES, resolve_credentials
from ..exceptions.custom_exceptions import ConnectionError


class SheetConnection:
    """Manages the connection to the Google Sheets API.

    Credentials are auto-resolved (cached `gsab auth login` token -> gcloud ADC
    -> service account). Inject your own with `credentials`, or point at a
    service-account file with `service_account_file` for servers/CI.
    """

    def __init__(
        self,
        credentials_path: Optional[str] = None,
        *,
        credentials=None,
        service_account_file: Optional[str] = None,
        scopes: Optional[Sequence[str]] = None,
        interactive: bool = False,
    ):
        self.credentials = credentials
        # `credentials_path` kept as a positional alias for service_account_file.
        self.service_account_file = service_account_file or credentials_path
        self.scopes = list(scopes) if scopes else list(DEFAULT_SCOPES)
        self.interactive = interactive
        self.service = None

    async def connect(self) -> None:
        """Resolve credentials (if needed) and build the Sheets service."""
        try:
            if self.credentials is None:
                self.credentials = resolve_credentials(
                    self.scopes,
                    service_account_file=self.service_account_file,
                    interactive=self.interactive,
                )
            self.service = build("sheets", "v4", credentials=self.credentials)
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Google Sheets API: {e}") from e

    def is_connected(self) -> bool:
        """Return True once the service has been built."""
        return self.service is not None
