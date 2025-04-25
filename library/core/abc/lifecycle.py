from abc import ABC, abstractmethod


class Lifecycle[T](ABC):
    @abstractmethod
    async def startup(self, *args, **kwargs) -> T: ...

    @abstractmethod
    async def shutdown(self): ...
