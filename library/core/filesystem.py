import mimetypes
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, Awaitable, Callable, Optional, Self

import aiofiles
import aioshutil
from aiofiles import os as async_os
from aiofiles import ospath as async_path
from pydantic import BaseModel

valid_path = re.compile(r"^/(.*/)*([^/]*)$")


class FilesystemPathError(Exception):
    pass


class FileSystemUsage(BaseModel):
    total: int
    used: int
    free: int


class FilesystemPath:
    def __init__(self, path: Path | str):
        self.path = Path(path)

        if path == Path() or path is None:
            raise FilesystemPathError("The given path is empty")

    async def exists(self) -> bool:
        return await async_path.exists(self.path)

    async def size(self) -> int:
        return await async_path.getsize(self.path)

    async def is_file(self) -> bool:
        return await async_path.isfile(self.path)

    async def is_directory(self) -> bool:
        return await async_path.isdir(self.path)

    async def created_at(self) -> datetime:
        unix_time = await async_path.getctime(self.path)

        return datetime.fromtimestamp(unix_time, tz=timezone.utc)

    async def modified_at(self) -> datetime:
        unix_time = await async_path.getmtime(self.path)

        return datetime.fromtimestamp(unix_time, tz=timezone.utc)

    def name(self) -> str:
        return self.path.name

    async def remove(self, shallow: bool = False, skip_errors: bool = False):
        try:
            if await self.exists() and await self.is_file() and not shallow:
                await aiofiles.os.remove(self.path)

            if await self.exists() and await self.is_directory() and not shallow:
                await aioshutil.rmtree(str(self.path))

        except OSError as e:
            if not skip_errors:
                raise FilesystemPathError(*e.args) from e

    async def generate_name(self, target_directory: Path, name: str) -> str:
        """Generate name based on target directory contents and self type."""
        count = 1
        new_path = target_directory.joinpath(name)

        while await async_path.exists(new_path):
            if await self.is_file():
                if with_counter := re.match(r"^(.+)\.(\d+)\.(\w+)$", new_path.name):
                    new_name, _, extension = with_counter.groups()

                elif with_extension := re.match(r"^(.+)\.(\w+)$", new_path.name):
                    new_name, extension = with_extension.groups()

                new_path = target_directory.joinpath(
                    "{}.{}.{}".format(new_name, count, extension)
                )

            if await self.is_directory():
                if with_counter := re.match(r"^(.+)\.(\d+)$", new_path.name):
                    new_name, _ = with_counter.groups()

                else:
                    new_name = new_path.name

                new_path = target_directory.joinpath("{}.{}".format(new_name, count))

            count += 1

        return new_path.name

    async def _generate_new_path(
        self,
        target_directory: Path,
        new_name: Optional[str] = None,
        force: bool = False,
        shallow: bool = False,
    ) -> Path:
        new_name = new_name or self.path.name

        if await async_path.exists(target_directory.joinpath(new_name)):
            if force or shallow:
                new_name = await self.generate_name(target_directory, new_name)

            else:
                raise FilesystemPathError("Target destination already exists")

        return target_directory.joinpath(new_name)

    async def move(
        self,
        target_directory: Path,
        new_name: Optional[str] = None,
        force: bool = False,
        shallow: bool = False,
    ) -> Self:
        new_path = await self._generate_new_path(
            target_directory, new_name, force=force, shallow=shallow
        )
        target = FilesystemPath(new_path)

        try:
            if await self.exists() and not shallow:
                await aioshutil.move(self.path, new_path)

        except Exception as e:
            raise FilesystemPathError(*e.args) from e

        return target

    async def rename(
        self, new_name: str, force: bool = False, shallow: bool = False
    ) -> Self:
        return await self.move(
            self.path.parent, new_name=new_name, force=force, shallow=shallow
        )

    async def copy(
        self,
        target_directory: Path,
        new_name: Optional[str] = None,
        force: bool = False,
        shallow: bool = False,
    ) -> Self:
        new_path = await self._generate_new_path(
            target_directory, new_name, force=force, shallow=shallow
        )
        target = FilesystemPath(new_path)

        try:
            if await self.is_file() and not shallow:
                await aioshutil.copy(self.path, new_path)

            if await self.is_directory() and not shallow:
                await aioshutil.copytree(self.path, new_path)

        except Exception as e:
            raise FilesystemPathError(*e.args) from e

        return target

    async def make_directory(self, force: bool = False):
        try:
            if await self.exists() and not force:
                raise FilesystemPathError("Already exists")

            await async_os.makedirs(self.path, exist_ok=force)

        except Exception as e:
            raise FilesystemPathError(*e.args)

    def open(
        self,
        mode="r",
        buffering=-1,
        encoding=None,
        errors=None,
        newline=None,
        closefd=True,
        opener=None,
        *,
        loop=None,
        executor=None,
    ):
        """
        Example:

        ```python
        async with FilesystemPath("example.txt").open(mode="r") as io:
            content = await io.read()
        print(content)
        ```
        """
        return aiofiles.open(
            self.path,
            mode=mode,
            buffering=buffering,
            encoding=encoding,
            errors=errors,
            newline=newline,
            closefd=closefd,
            opener=opener,
            loop=loop,
            executor=executor,
        )

    async def write_file(self, data: bytes, force: bool = False):
        try:
            if await self.exists() and not force:
                raise FilesystemPathError("Already exists")

            async with self.open(mode="wb") as file:
                await file.write(data)

        except Exception as e:
            raise FilesystemPathError(*e.args)

    @staticmethod
    def validate_path(path: Path) -> bool:
        return bool(valid_path.match(str(path)))

    @staticmethod
    def normalize(path: Path) -> Path:
        """Resolve path and make it relative."""
        if not path.is_absolute():
            path = Path("/").joinpath(path)

        return Path(*path.resolve().parts[1:])

    async def walk_files(
        self, current_path: Optional[Path] = None
    ) -> AsyncGenerator[Path, None]:
        # TODO: make benchmark tests
        if not current_path:
            current_path = self.path

        paths = await async_os.listdir(current_path)

        for path in paths:
            child_path = current_path.joinpath(path)

            if await async_path.isfile(child_path):
                yield child_path

            elif await async_path.isdir(child_path):
                async for nested_path in self.walk_files(child_path):
                    yield nested_path

    def sync_walk_files(self, current_path: Optional[Path] = None):
        if not current_path:
            current_path = self.path

        paths = os.listdir(current_path)

        for path in paths:
            child_path = current_path.joinpath(path)

            if os.path.isfile(child_path):
                yield child_path

            elif os.path.isdir(child_path):
                for nested_path in self.sync_walk_files(child_path):
                    yield nested_path

    async def disk_usage(self) -> int:
        sum = 0

        async for path in self.walk_files():
            sum += await async_path.getsize(path)

        return sum

    def sync_disk_usage(self) -> int:
        sum = 0

        for path in self.sync_walk_files():
            sum += os.path.getsize(path)

        return sum

    async def mime_disk_usage(self, mime_types: list[str] = []) -> dict[str, int]:
        mime_usage = {mime: 0 for mime in mime_types}

        async for path in self.walk_files():
            mime_type, _ = mimetypes.guess_type(path)

            if mime_type in mime_types:
                mime_usage[mime_type] += await async_path.getsize(path)

        return mime_usage

    async def remove_files(
        self,
        filter: Optional[Callable[..., Awaitable[bool]]],
        skip_errors: bool = False,
    ):
        """
        Example:

        ```python
        from datetime import datetime, timezone, timedelta
        import asyncio

        async def purge_logs():
            await FilesystemPath("logs").remove_files(lambda fs: datetime.now(tz=timezone.utc) - timedelta(days=30) > fs.created_at())

        asyncio.run(purge_logs())
        ```
        """
        async for path in self.walk_files():
            if filter:
                if await filter(FilesystemPath(path)):
                    await FilesystemPath(path).remove(skip_errors=skip_errors)
            else:
                await FilesystemPath(path).remove(skip_errors=skip_errors)
