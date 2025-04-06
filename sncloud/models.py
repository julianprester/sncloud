from typing import Annotated, Literal
from pydantic import BaseModel, Field, BeforeValidator
from datetime import datetime, timezone

def convert_timestamp(epoch: int) -> datetime:
    """Convert millisecond timestamp to datetime"""
    return datetime.fromtimestamp(epoch / 1000).astimezone(timezone.utc)

class CloudItem(BaseModel):
    id: int
    directory_id: int = Field(alias='directoryId')
    file_name: str = Field(alias='fileName')
    size_: int = Field(alias='size')
    md5: str
    is_folder: Literal["Y", "N"] = Field(alias='isFolder')
    create_time: Annotated[datetime, BeforeValidator(convert_timestamp)] = Field(alias='createTime')
    update_time: Annotated[datetime, BeforeValidator(convert_timestamp)] = Field(alias='updateTime')

class File(CloudItem):
    is_folder: Literal["N"] = "N"

class Directory(CloudItem):
    is_folder: Literal["Y"] = "Y"
