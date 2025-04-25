import contextlib
import inspect
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, AsyncIterator, Optional, Self, cast

from fastapi import FastAPI
from pydantic import BaseModel
from taskiq_dependencies import DependencyGraph
from taskiq_dependencies import Depends as LifespanDepends
from taskiq_dependencies.graph import Dependency

__all__ = ["Lifespan", "LifespanError", "LifespanDepends"]

LifespanStateCallable = Callable[..., AsyncIterator[Any]]


class LifespanState(BaseModel):
    func: LifespanStateCallable
    state_name: Optional[str] = None


class LifespanError(Exception): ...


class Lifespan:
    def __init__(
        self,
        states: list[LifespanState] = [],
    ) -> None:
        self.states: list[LifespanState] = []
        self._exit_stack = None
        self._states_store: dict[str, Any] = {}

        for state in states:
            self.add_state(state.func, state.state_name)

    @asynccontextmanager
    async def __call__(
        self, app: Optional[FastAPI] = None
    ) -> AsyncGenerator[dict[str, Any], None]:
        exit_stack = contextlib.AsyncExitStack()
        states_store = {}
        cache = {}

        async with exit_stack:
            for state in self.states:
                graph = DependencyGraph(state.func)

                async with graph.async_ctx(initial_cache=cache) as ctx:
                    kwargs = await ctx.resolve_kwargs()

                for dep, _ in graph.dependencies.items():
                    dep = cast(Dependency, dep)
                    cache[dep.dependency] = kwargs.get(dep.param_name)

                sig = inspect.signature(graph.target)

                if app is not None:
                    for key, param in sig.parameters.items():
                        if param.annotation and param.annotation is FastAPI:
                            kwargs[key] = app

                try:
                    evaluated_state = await exit_stack.enter_async_context(
                        asynccontextmanager(graph.target)(**kwargs)
                    )

                except Exception as e:
                    raise LifespanError(*e.args) from e

                if state.state_name is not None:
                    states_store[state.state_name] = evaluated_state

                cache[graph.target] = evaluated_state

            yield states_store

    async def unwind(self) -> Self:
        self._exit_stack = contextlib.AsyncExitStack()
        self._states_store = await self._exit_stack.enter_async_context(self.__call__())

        return self

    @property
    def unwinded(self) -> bool:
        return bool(self._exit_stack)

    @property
    def states_store(self) -> dict[str, Any]:
        return self._states_store

    async def dispose(self) -> Self:
        if self._exit_stack:
            await self._exit_stack.aclose()
            self._states_store = {}

        return self

    def add_state(
        self,
        func: LifespanStateCallable,
        state_name: Optional[str] = None,
    ):
        if state_name is not None:
            for state in self.states:
                if state.state_name is not None and state.state_name == state_name:
                    raise LifespanError(
                        f"The state name '{state_name}' is already used by {state.func}"
                    )

        self.states.append(LifespanState(func=func, state_name=state_name))

    def state(
        self, state_name: Optional[str] = None
    ) -> Callable[
        [LifespanStateCallable],
        LifespanStateCallable,
    ]:
        def decorator(
            func: LifespanStateCallable,
        ) -> LifespanStateCallable:
            self.add_state(func=func, state_name=state_name)

            return func

        return decorator

    def include_lifespan(self, lifespan: Self) -> Self:
        for state in lifespan.states:
            self.add_state(func=state.func, state_name=state.state_name)

        return self
