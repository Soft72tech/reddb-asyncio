from typing import (
    Any,
    Callable,
    Optional,
    Self,
)

from redis.exceptions import ConnectionError
from taskiq import AsyncTaskiqDecoratedTask, TaskiqScheduler
from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend, RedisScheduleSource

from library.core.abc.task_manager import AsyncTaskManager, TaskManagerError
from library.core.configs import RedisConfig


class AsyncRedisTaskManager(AsyncTaskManager):
    def __init__(self, config: RedisConfig, **connection_kwargs):
        _connection_kwargs = {}
        _connection_kwargs.update(connection_kwargs)

        self.config: RedisConfig = config
        self.result_backend: RedisAsyncResultBackend = RedisAsyncResultBackend(
            redis_url=config.to_string_url()
        )
        self.broker: ListQueueBroker = ListQueueBroker(
            url=config.to_string_url(), **_connection_kwargs
        ).with_result_backend(self.result_backend)

        self.scheduler: TaskiqScheduler = TaskiqScheduler(
            self.broker, sources=[RedisScheduleSource(config.to_string_url())]
        )

    async def test_connection(self):
        try:
            connection = self.broker.connection_pool.make_connection()

            await connection.connect()

        except ConnectionError as e:
            raise TaskManagerError(*e.args) from e

        else:
            await connection.disconnect()

    async def startup(self):
        await self.broker.startup()
        await self.scheduler.startup()

    async def shutdown(self):
        await self.broker.shutdown()
        await self.scheduler.shutdown()

    def register_task[R](
        self,
        func: Callable[..., R],
        task_name: Optional[str] = None,
        **labels: Any,
    ) -> Self:
        self.broker.register_task(func, task_name=task_name, **labels)

        return self

    def find_task(self, task_name: str) -> Optional[AsyncTaskiqDecoratedTask[Any, Any]]:
        return self.broker.find_task(task_name=task_name)
