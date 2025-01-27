from pathlib import Path
import httpx
from typing import Optional, Dict, Any, Tuple, List, Union
import os

from hashlib import sha256, md5

from sncloud.models import File, Directory
from sncloud import endpoints
from sncloud.exceptions import ApiError, AuthenticationError

__version__ = "0.1.0"

def calc_sha256(text: str) -> str:
    """
    Calculate SHA256 hash of input string.

    Args:
        text: Input string to hash

    Returns:
        str: Hexadecimal representation of hash
    """
    return sha256(text.encode("utf-8")).hexdigest()


def calc_md5(data: Union[str, bytes]) -> str:
    """
    Calculate MD5 hash of input string or bytes.

    Args:
        data: Input string or bytes to hash

    Returns:
        str: Hexadecimal representation of hash

    Raises:
        TypeError: If input is neither string nor bytes
    """
    if isinstance(data, str):
        return md5(data.encode("utf-8")).hexdigest()
    elif isinstance(data, bytes):
        return md5(data).hexdigest()
    else:
        raise TypeError("Input must be string or bytes")


class SNClient:
    BASE_URL = "https://cloud.supernote.com/api"

    def __init__(self):
        self._client = httpx.Client()
        self._access_token: Optional[str] = None

    def _api_call(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make an API call to the specified endpoint with the given payload.

        Args:
            endpoint: API endpoint path
            payload: Request payload/body

        Returns:
            Dict containing the API response

        Raises:
            requests.exceptions.RequestException: If the request fails
        """
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
        }
        if self._access_token:
            headers["x-access-token"] = self._access_token

        response = self._client.post(
            f"{self.BASE_URL}{endpoint}", json=payload, headers=headers
        )
        response.raise_for_status()
        return response.json()

    def _get_random_code(self, email: str) -> Tuple[str, str]:
        """
        Get a random login code for the specified email address.
        Return the random code and timestamp.

        Args:
            email: User's email address

        Returns:
            Tuple: The random code and timestamp

        Raises:
            ApiError: If the request fails
        """
        payload = {"countryCode": "1", "account": email}

        data = self._api_call(endpoints.code, payload)
        if not data["success"]:
            raise ApiError("Failed to get random code")
        return (data["randomCode"], data["timestamp"])

    def login(self, email: str, password: str) -> str:
        """
        Authenticate with Supernote Cloud using email and password.
        Returns access token on success.

        Args:
            email: User's email address
            password: User's password

        Returns:
            str: Access token

        Raises:
            AuthenticationError: If login fails
        """
        (rc, timestamp) = self._get_random_code(email)

        pd = calc_sha256(calc_md5(password) + rc)
        payload = {
            "countryCode": 1,
            "account": email,
            "password": pd,
            "browser": "Chrome107",
            "equipment": "1",
            "loginMethod": "1",
            "timestamp": timestamp,
            "language": "en",
        }

        data = self._api_call(endpoints.login, payload)
        if not data["success"]:
            raise AuthenticationError(data["errorMsg"])
        self._access_token = data["token"]
        return data["token"]

    def ls(self, directory: Union[int, Directory] = 0) -> List[Union[File, Directory]]:
        """
        List files and folders in the specified directory.
        If no directory specified, lists root directory.

        Args:
            id: Directory id (optional)

        Returns:
            List of File and Directory objects

        Raises:
            AuthenticationError: If not authenticated
        """
        if not self._access_token:
            raise AuthenticationError("Must be authenticated to list files")

        payload = {
            "directoryId": directory.id
            if isinstance(directory, Directory)
            else directory,
            "pageNo": 1,
            "pageSize": 100,
            "order": "time",
            "sequence": "desc",
        }

        data = self._api_call(endpoints.ls, payload)
        return [
            Directory(**item) if item["isFolder"] == "Y" else File(**item)
            for item in data["userFileVOList"]
        ]

    def get(self, item: Union[int, File], path: Path = Path(".")) -> str:
        """
        Download a single file by its ID.

        Args:
            item: file or file id to download

        Returns:
            str: Path where file was saved

        Raises:
            AuthenticationError: If not authenticated
            ApiError: If download fails
        """
        if not self._access_token:
            raise AuthenticationError("Must be authenticated to download files")

        payload = {"id": item.id if isinstance(item, File) else item, "type": 0}

        data = self._api_call(endpoints.get, payload)
        if not data["success"]:
            raise ApiError(data["errorMsg"])
        response = self._client.get(data["url"])
        buffer = response.content

        with open(path / Path(item.file_name), "wb") as f:
            f.write(buffer)

        return path / Path(item.file_name)

    def get_pdf(
        self, item: File, path: Path = Path("."), page_numbers: List[int] = []
    ) -> str:
        """
        Download a single note file as a PDF.

        Args:
            id: ID of the file to convert to PDF and download
            page_numbers: List of page numbers to include

        Returns:
            str: Path where PDF file was saved

        Raises:
            ValueError: If not authenticated
            ApiError: If download fails
        """
        if not self._access_token:
            raise AuthenticationError("Must be authenticated to download files")

        payload = {"id": item.id, "pageNoList": page_numbers}

        data = self._api_call(endpoints.get_pdf, payload)
        if not data["success"]:
            raise ApiError(data["errorMsg"])
        response = self._client.get(data["url"])
        response.raise_for_status()

        with open(path / Path(item.file_name[:-5] + ".pdf"), "wb") as f:
            f.write(response.content)

        return path / Path(item.file_name)

    def get_png(
        self, item: File, path: Path = Path("."), page_numbers: List[int] = []
    ) -> List[str]:
        """
        Download a single note file as pngs.

        Args:
            id: ID of the file to convert to PNGs and download
            page_numbers: List of page numbers to include

        Returns:
            List[str]: Paths where PNG files were saved

        Raises:
            ValueError: If not authenticated
            ApiError: If download fails
        """
        if not self._access_token:
            raise AuthenticationError("Must be authenticated to download files")

        payload = {"id": item.id}

        data = self._api_call(endpoints.get_png, payload)
        if not data["success"]:
            raise ApiError(data["errorMsg"])
        pngs = {png["pageNo"]: png["url"] for png in data["pngPageVOList"]}
        if not page_numbers:
            page_numbers = list(pngs.keys())
        for page in page_numbers:
            response = self._client.get(pngs[page])
            response.raise_for_status()

            with open(path / Path(item.file_name + f"_{page}.png"), "wb") as f:
                f.write(response.content)

        return path / Path(item.file_name + ".png")

    def mkdir(self, parent: Union[int, Directory], folder_name: str) -> str:
        """Create a new folder in the parent directory.

        Args:
            parent: Parent directory id
            folder_name: Name of the folder to create

        Returns:
            str: Name of created folder

        Raises:
            AuthenticationError: If not authenticated
            ApiError: If folder creation fails
        """
        if not self._access_token:
            raise AuthenticationError("Must be authenticated to download files")

        payload = {
            "directoryId": parent.id if isinstance(parent, Directory) else parent,
            "fileName": folder_name,
        }

        data = self._api_call(endpoints.mkdir, payload)
        if not data["success"]:
            raise ApiError(data["errorMsg"])

        return folder_name

    def put(self, file_path: Path, parent: Union[int, Directory] = 0) -> str:
        """Upload a file to the parent directory.

        Args:
            file_path: Path to the file to upload
            parent: Parent directory id

        Returns:
            str: Name of uploaded file

        Raises:
            AuthenticationError: If not authenticated
            FileNotFoundError: If file not found
            ApiError: If file upload fails
        """
        if not self._access_token:
            raise AuthenticationError("Must be authenticated to download files")
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path, "rb") as f:
            file_data = f.read()
            data_md5 = calc_md5(file_data)

        payload = {
            "directoryId": parent.id if isinstance(parent, Directory) else parent,
            "fileName": file_path.name,
            "md5": data_md5,
            "size": len(file_data),
        }
        data = self._api_call(endpoints.upload_apply, payload)

        if not data["success"]:
            raise ApiError(data["errorMsg"])
            
        aws_headers = {
            "Authorization": data["s3Authorization"],
            "x-amz-date": data["xamzDate"],
            "x-amz-content-sha256": "UNSIGNED-PAYLOAD",
        }
        response = self._client.put(data["url"], data=file_data, headers=aws_headers)
        if response.status_code != 200:
            raise ApiError(data.text)
        inner_name = os.path.basename(data["url"])
        payload = {
            "directoryId": parent.id if isinstance(parent, Directory) else parent,
            "fileName": file_path.name,
            "fileSize": len(file_data),
            "innerName": inner_name,
            "md5": data_md5,
        }
        self._api_call(endpoints.upload_finish, payload)
