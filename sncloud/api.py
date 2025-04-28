from pathlib import Path
import httpx
from typing import Optional, Dict, Any, Tuple, List, Union
import os

from hashlib import sha256, md5

from sncloud.models import File, Directory
from sncloud import endpoints
from sncloud.exceptions import ApiError, AuthenticationError, FileFolderNotFound

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
        self._client = httpx.Client(timeout=60)
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

    def _get_directory_id(self, directory: Union[None, int, str, Directory] = None) -> int:
        """
        Convert various directory representations to a directory ID.
        
        Args:
            directory: Directory path, object, ID, or None/0/"/" for root
            
        Returns:
            int: Directory ID (0 for root)
            
        Raises:
            ValueError: If directory is an invalid type
            FileFolderNotFound: If directory path doesn't exist
        """
        # Handle root directory cases
        if directory is None or directory == 0 or directory == "/":
            return 0
            
        # Convert string paths to Directory objects
        if isinstance(directory, str):
            directory = self._get_item(directory)
            
        # Extract ID from Directory object
        if isinstance(directory, Directory):
            return directory.id
            
        # Handle direct integer IDs
        if isinstance(directory, int):
            return directory
            
        raise ValueError(f"Invalid directory type: {type(directory)}")

    def _get_item(self, item: Union[str, File, Directory]) -> Union[File, Directory]:
        """
        Get the item by its path or object.

        Args:
            item: File or Directory object or path
        Returns:
            File or Directory object
        Raises:
            FileFolderNotFound: If the item is not found
            TypeError: If item is an invalid type
        """
        # Return the item directly if it's already a File or Directory object
        if isinstance(item, (File, Directory)):
            return item
            
        if isinstance(item, str):
            # Handle root directory case
            if item == "/":
                # Return first item's parent from root directory
                # This is a workaround since we don't have a direct way to get root directory
                items = self.ls()
                if items:
                    return items[0].parent
                return Directory(id=0, file_name="/", parent_id=None)  # Fallback
                
            # Process path string
            item_path = Path(item)
            parts = item_path.parts
            
            # Handle absolute vs relative paths
            if parts and (parts[0] == "/" or parts[0] == "\\"):
                parts = parts[1:]  # Remove leading slash for absolute paths
                
            # Empty path or just "/" returns root directory
            if not parts:
                return Directory(id=0, file_name="/", parent_id=None)  # Root directory
                
            # Check if the last part has an extension to determine if it's a file
            is_file = "." in parts[-1] if parts else False
            dir_parts = parts[:-1] if is_file else parts
            
            # Navigate through directories
            current_dir = None  # Start at root
            current_items = self.ls(current_dir)
            
            for i, part in enumerate(dir_parts):
                found = False
                
                for item in current_items:
                    if item.file_name == part and isinstance(item, Directory):
                        current_dir = item
                        found = True
                        current_items = self.ls(current_dir)
                        break
                        
                if not found:
                    path_so_far = "/" + "/".join(parts[:i+1])
                    raise FileFolderNotFound(f"Directory not found: {part} in {path_so_far}")
                    
            # If we're looking for a file, find it in the final directory
            if is_file:
                for item in current_items:
                    if item.file_name == parts[-1]:
                        return item
                raise FileFolderNotFound(f"File not found: {parts[-1]} in /{'/'.join(dir_parts)}")
            
            # Return the directory we found
            return current_dir
        
        # If we get here, item is of an unsupported type
        raise TypeError(f"Expected string path or File/Directory object, got {type(item)}")

    def ls(self, directory: Union[None, int, str, Directory] = None) -> List[Union[File, Directory]]:
        """
        List files and folders in the specified directory.
        If no directory specified, lists root directory.

        Args:
            directory: Directory ID, path, Directory object, or None for root

        Returns:
            List of File and Directory objects

        Raises:
            AuthenticationError: If not authenticated
            FileFolderNotFound: If directory doesn't exist
        """
        if not self._access_token:
            raise AuthenticationError("Must be authenticated to list files")

        dir_id = self._get_directory_id(directory)
        
        payload = {
            "directoryId": dir_id,
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

    def get(self, item: Union[str, File], path: Path = Path(".")) -> str:
        """
        Download a single file.

        Args:
            item: file path or object to download

        Returns:
            str: Path where file was saved

        Raises:
            AuthenticationError: If not authenticated
            ApiError: If download fails
        """
        if not self._access_token:
            raise AuthenticationError("Must be authenticated to download files")
        
        item = self._get_item(item)

        payload = {"id": item.id, "type": 0}

        data = self._api_call(endpoints.get, payload)
        if not data["success"]:
            raise ApiError(data["errorMsg"])
        response = self._client.get(data["url"])
        buffer = response.content

        with open(path / Path(item.file_name), "wb") as f:
            f.write(buffer)

        return path / Path(item.file_name)

    def get_pdf(
        self, item: Union[str, File], path: Path = Path("."), page_numbers: List[int] = []
    ) -> str:
        """
        Download a single note file as a PDF.

        Args:
            item: file path or object of the file to convert to PDF and download
            page_numbers: List of page numbers to include

        Returns:
            str: Path where PDF file was saved

        Raises:
            ValueError: If not authenticated
            ApiError: If download fails
        """
        if not self._access_token:
            raise AuthenticationError("Must be authenticated to download files")

        item = self._get_item(item)

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
        self, item: Union[str, File], path: Path = Path("."), page_numbers: List[int] = []
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

        item = self._get_item(item)

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

    def mkdir(self, folder_name: str, parent: Union[None, str, Directory] = None) -> str:
        """Create a new folder in the parent directory.

        Args:
            folder_name: Name of the folder to create
            parent: Parent directory path, object, or None for root

        Returns:
            str: Name of created folder

        Raises:
            AuthenticationError: If not authenticated
            ApiError: If folder creation fails
        """
        if not self._access_token:
            raise AuthenticationError("Must be authenticated to create folders")

        dir_id = self._get_directory_id(parent)
        
        payload = {
            "directoryId": dir_id,
            "fileName": folder_name,
        }

        data = self._api_call(endpoints.mkdir, payload)
        if not data["success"]:
            raise ApiError(data["errorMsg"])

        return folder_name

    def put(self, file_path: Path, parent: Union[None, str, Directory] = None) -> str:
        """Upload a file to the parent directory.

        Args:
            file_path: Path to the file to upload
            parent: Parent directory path, object, or None for root

        Returns:
            str: Name of uploaded file

        Raises:
            AuthenticationError: If not authenticated
            FileNotFoundError: If file not found
            ApiError: If file upload fails
        """
        if not self._access_token:
            raise AuthenticationError("Must be authenticated to upload files")
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path, "rb") as f:
            file_data = f.read()
            data_md5 = calc_md5(file_data)

        dir_id = self._get_directory_id(parent)

        payload = {
            "directoryId": dir_id,
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
            "directoryId": dir_id,
            "fileName": file_path.name,
            "fileSize": len(file_data),
            "innerName": inner_name,
            "md5": data_md5,
        }
        self._api_call(endpoints.upload_finish, payload)

    def delete(self, item: Union[str, File, Directory, list[Union[str, File, Directory]]]) -> list[str]:
        """Delete a file or list of files.

        Args:
            item: file or list of files to be deleted

        Returns:
            str: Name(s) of deleted file(s)

        Raises:
            AuthenticationError: If not authenticated
            FileNotFoundError: If file not found
            ApiError: If file upload fails
        """
        if not self._access_token:
            raise AuthenticationError("Must be authenticated to upload files")
        
        if isinstance(item, list):
            to_delete = [self._get_item(i) for i in item]
            dir_id = to_delete[0].directory_id
            for i in to_delete:
                if i.directory_id != dir_id:
                    raise FileFolderNotFound(f"Files are not in the same directory: {i.file_name}")
        else:
            to_delete = [self._get_item(item)]

        payload = {
            "directoryId": to_delete[0].directory_id,
            "idList": [i.id for i in to_delete]
        }
        data = self._api_call(endpoints.delete, payload)
        if not data["success"]:
            raise ApiError(data["errorMsg"])

        return ", ".join([i.file_name for i in to_delete])
