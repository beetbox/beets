"""Unit tests for the async state machine."""

import asyncio
from dataclasses import dataclass, field
from typing import AsyncGenerator, Coroutine, Generator

import pytest
import pytest_asyncio

from beets.util.async_state_machine import (
    AsyncStateMachine,
    State,
    StateTaskHandler,
)


@dataclass
class Task:
    value: int
    states: list[str] = field(default_factory=list)


def async_generator_handler(state: str) -> StateTaskHandler[Task]:
    async def handler(task: Task) -> AsyncGenerator[Task, None]:
        assert isinstance(task, Task)
        task.states.append(state)
        yield task

    return handler


def generator_handler(state: str) -> StateTaskHandler[Task]:
    def handler(task: Task) -> Generator[Task, None, None]:
        assert isinstance(task, Task)
        task.states.append(state)
        yield task

    return handler


def coroutine_handler(state: str) -> StateTaskHandler[Task]:
    async def handler(task: Task) -> Coroutine[Task, None, None]:
        assert isinstance(task, Task)
        task.states.append(state)
        return task

    return handler


def handler_for(state: str) -> StateTaskHandler[Task]:
    def handler(task: Task) -> Task:
        assert isinstance(task, Task)
        task.states.append(state)
        return task

    return handler


@pytest_asyncio.fixture
async def sm() -> AsyncGenerator[AsyncStateMachine[Task], None]:
    """Create a simple test state machine."""

    always = lambda _: True

    transition_graph = (
        (
            State(
                id="INIT",
                max_queue_size=1,
                handler=handler_for("INIT"),
            ),
            (("PROCESS", always),),
        ),
        (
            State(
                id="PROCESS",
                max_queue_size=2,
                handler=handler_for("PROCESS"),
            ),
            (("FINAL", always),),
        ),
        (
            State(
                id="FINAL",
                max_queue_size=1,
                handler=handler_for("FINAL"),
                accumulate=True,
            ),
            tuple(),
        ),
    )

    async with AsyncStateMachine(transition_graph) as machine:
        yield machine


@pytest.mark.asyncio
async def test_nominal_processing(sm: AsyncStateMachine[Task]):
    """Test nominal processing of tasks."""
    n = 5
    inject_tasks = [
        asyncio.create_task(
            sm.inject(Task(value=i), "INIT"),
            name=f"test_nominal_processing-inject-{i}",
        )
        for i in range(n)
    ]

    async def accumulate_and_assert():
        i = 0
        async for output in sm.accumulated("FINAL"):
            assert output.value == i
            assert output.states == ["INIT", "PROCESS", "FINAL"]
            i += 1
        assert i == n

    assert_task = asyncio.create_task(
        accumulate_and_assert(),
        name="test_nominal_processing-accumulate_and_assert",
    )

    await asyncio.gather(*inject_tasks, assert_task)


@pytest.mark.asyncio
async def test_invalid_transition():
    """Test handling of invalid state transitions."""
    transition_graph = (
        (
            State(
                id="INIT",
                max_queue_size=1,
                handler=handler_for("INIT"),
            ),
            (("INVALID", lambda _: True),),  # Invalid state reference
        ),
    )

    with pytest.raises(ValueError):
        AsyncStateMachine(transition_graph)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "handler",
    [
        async_generator_handler("INIT"),  # Async generator
        generator_handler("INIT"),  # Generator
        coroutine_handler("INIT"),  # Coroutine
        handler_for("INIT"),  # Regular function
    ],
)
async def test_handler_types(handler):
    """Test that handlers can be of different types."""
    transition_graph = (
        (
            State(
                id="INIT",
                max_queue_size=1,
                handler=handler,
                accumulate=True,
            ),
            tuple(),
        ),
    )

    async with AsyncStateMachine(transition_graph) as machine:
        await machine.inject(Task(value=1), "INIT")
        async for output in machine.accumulated("INIT"):
            assert output.value == 1
            assert output.states == ["INIT"]


@pytest.mark.asyncio
async def test_terminal_state():
    """Test behavior when reaching a terminal state."""
    transition_graph = (
        (
            State(
                id="INIT",
                max_queue_size=1,
                handler=handler_for("INIT"),
            ),
            (("FINAL", lambda _: True),),
        ),
        (
            State(
                id="FINAL",
                max_queue_size=1,
                handler=handler_for("FINAL"),
                accumulate=True,
            ),
            tuple(),
        ),
    )

    async with AsyncStateMachine(transition_graph) as machine:
        await machine.inject(Task(value=1), "INIT")

        async for output in machine.accumulated("FINAL"):
            assert output.value == 1
            assert output.states == ["INIT", "FINAL"]


@pytest.mark.asyncio
async def test_error_handling():
    """Test error handling in state handlers."""

    async def error_handler(task: Task) -> AsyncGenerator[Task, None]:
        task.states.append("ERROR")
        if True:
            raise ValueError("Test error")
        else:
            yield task

    transition_graph = (
        (
            State(
                id="INIT",
                max_queue_size=1,
                handler=handler_for("INIT"),
            ),
            (("ERROR", lambda t: True),),
        ),
        (
            State(
                id="ERROR",
                max_queue_size=1,
                handler=error_handler,
            ),
            tuple(),
        ),
    )

    with pytest.raises(ValueError):
        async with AsyncStateMachine(transition_graph) as machine:
            await machine.inject(Task(value=1), "INIT")


@pytest.mark.asyncio
async def test_multiple_task_yielding():
    """Test that handlers can yield multiple new tasks."""

    async def multi_yield_handler(task: Task) -> AsyncGenerator[Task, None]:
        task.states.append("MULTI")
        # Yield multiple new tasks
        for i in range(3):
            new_task = Task(value=i)
            new_task.states.append("MULTI")
            yield new_task

    transition_graph = (
        (
            State(
                id="INIT",
                max_queue_size=1,
                handler=handler_for("INIT"),
            ),
            (("MULTI", lambda _: True),),
        ),
        (
            State(
                id="MULTI",
                max_queue_size=3,
                handler=multi_yield_handler,
            ),
            (("FINAL", lambda _: True),),
        ),
        (
            State(
                id="FINAL",
                max_queue_size=3,
                handler=handler_for("FINAL"),
                accumulate=True,
            ),
            tuple(),
        ),
    )

    async with AsyncStateMachine(transition_graph) as machine:
        # Inject initial task
        task = Task(value=1)
        await machine.inject(task, "INIT")

        # Collect and verify the accumulated outputs
        values = []
        async for output in machine.accumulated("FINAL"):
            values.append(output.value)
            assert output.states == ["MULTI", "FINAL"]
        assert sorted(values) == [0, 1, 2]

        # Verify the initial task went through INIT and MULTI
        assert task.states == ["INIT", "MULTI"]


@pytest.mark.asyncio
async def test_cyclic_state_graph():
    """Test that state machines can handle cyclic state graphs with multiple paths."""
    transition_graph = (
        (
            State(
                id="INIT",
                max_queue_size=5,
                handler=handler_for("INIT"),
            ),
            (
                ("CYCLE", lambda t: "CYCLE" not in t.states),
                ("END", lambda t: "CYCLE" in t.states),
            ),
        ),
        (
            State(
                id="CYCLE",
                max_queue_size=5,
                handler=handler_for("CYCLE"),
            ),
            (("INIT", lambda _: True),),
        ),
        (
            State(
                id="END",
                max_queue_size=5,
                handler=handler_for("END"),
            ),
            tuple(),
        ),
    )

    async with AsyncStateMachine(transition_graph) as machine:
        # Inject initial task
        task = Task(value=0)
        await machine.inject(task, "INIT")
        await machine.join()

        # Verify the initial task went through INIT
        assert task.states == ["INIT", "CYCLE", "INIT", "END"]
