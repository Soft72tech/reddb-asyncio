import shutil
from pathlib import Path
from typing import Self

from pydantic import BaseModel
from sqlmodel import SQLModel

from library.core.abc.database import AsyncDatabase
from library.core.converters import UnitValue, UnitValuePercent, convert_bytes
from library.core.filesystem import FilesystemPath


class FilesystemUsage(SQLModel):
    total: int
    free: int
    used: int


class FilesystemUnitUsage(BaseModel):
    total: UnitValue
    free: UnitValue
    used: UnitValue


class DataUsage(BaseModel):
    database: UnitValuePercent
    video: UnitValuePercent
    images: UnitValuePercent
    logs: UnitValuePercent


class FilesystemStats(SQLModel):
    host: FilesystemUnitUsage
    data_usage: DataUsage

    @classmethod
    def filesystem_usage(cls, monitoring_filesystem: Path) -> FilesystemUsage:
        path = Path("/rootfs").joinpath(
            str(monitoring_filesystem).lstrip(monitoring_filesystem.root)
        )

        if not path.exists():
            return FilesystemUsage(total=0, free=0, used=0)

        usage = shutil.disk_usage(path)

        return FilesystemUsage(total=usage.total, free=usage.free, used=usage.used)

    @classmethod
    async def new(
        cls,
        database: AsyncDatabase,
        monitoring_filesystem: Path,
        data_directory: Path,
        log_directory: Path,
    ) -> Self:
        data_dir = FilesystemPath(data_directory)
        log_dir = FilesystemPath(log_directory)
        mime_types = ["image/png", "image/jpeg", "video/mp4"]

        mime_du = await data_dir.mime_disk_usage(mime_types)
        images_du, video_du = 0, 0

        for mime, size in mime_du.items():
            if mime.startswith("image"):
                images_du += size

            if mime.startswith("video"):
                video_du += size

        database_du = await database.usage()

        log_du = 0

        async for file in log_dir.walk_files():
            log_du += await FilesystemPath(file).size()

        host_stats = cls.filesystem_usage(monitoring_filesystem)

        du = DataUsage(
            database=UnitValuePercent(
                **convert_bytes(database_du).model_dump(),
                usage_percent=database_du / host_stats.used
                if host_stats and host_stats.used != 0
                else 0,
            ),
            video=UnitValuePercent(
                **convert_bytes(video_du).model_dump(),
                usage_percent=video_du / host_stats.used
                if host_stats and host_stats.used != 0
                else 0,
            ),
            images=UnitValuePercent(
                **convert_bytes(images_du).model_dump(),
                usage_percent=images_du / host_stats.used
                if host_stats and host_stats.used != 0
                else 0,
            ),
            logs=UnitValuePercent(
                **convert_bytes(log_du).model_dump(),
                usage_percent=log_du / host_stats.used
                if host_stats and host_stats.used != 0
                else 0,
            ),
        )

        return FilesystemStats(
            host=FilesystemUnitUsage(
                total=convert_bytes(host_stats.total if host_stats else 0),
                free=convert_bytes(host_stats.free if host_stats else 0),
                used=convert_bytes(host_stats.used if host_stats else 0),
            ),
            data_usage=du,
        )
