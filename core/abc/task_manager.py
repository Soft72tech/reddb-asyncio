from abc import ABC, abstractmethod


class TaskManagerError(Exception): ...


class AsyncTaskManager(ABC):
    @abstractmethod
    async def test_connection(self): ...
