"""State machine implementation for the beets import process.

This module provides a generic, concurrent, state-machine-based task processing system.

Example usage:

```python
from dataclasses import dataclass, field

@dataclass
class ImageTask:
    data: bytes
    size: int
    thumbnail: Optional[bytes] = None
    processed: Optional[bytes] = None
    error: Optional[str] = None

async def read_image(task: ImageTask) -> AsyncGenerator[ImageTask, None]:
    if not task.data:
        task.error = "Empty image data"
    yield task

async def process_small_image(task: ImageTask) -> AsyncGenerator[ImageTask, None]:
    # Simulate light processing
    await asyncio.sleep(0.1)
    task.processed = task.data
    yield task

async def process_large_image(task: ImageTask) -> AsyncGenerator[ImageTask, None]:
    # Simulate heavy processing
    await asyncio.sleep(0.5)
    task.processed = task.data
    yield task

async def create_thumbnail(task: ImageTask) -> AsyncGenerator[ImageTask, None]:
    # Simulate thumbnail creation
    await asyncio.sleep(0.2)
    task.thumbnail = task.processed[:100]
    yield task

# Define the state machine's transition graph
transition_graph = {
    State(
        id="READ",
        max_queue_size=10,  # Cap incoming images to manage memory requirements
        concurrency=2,      # Parse multiple images concurrently
        handler=read_image,
    ): {
        # Route to error state if there's an error
        "ERROR": lambda t: t.error,
        # Route based on image size
        "PROCESS_SMALL": lambda t: t.size < 1024 * 1024,
        "PROCESS_LARGE": lambda t: t.size >= 1024 * 1024,
    },
    State(
        id="PROCESS_SMALL",
        max_queue_size=20,   # More queue capacity for quick processing
        concurrency=4,       # High concurrency for light tasks
        handler=process_small_image,
    ): {
        "THUMBNAIL": lambda _: True,
    },
    State(
        id="PROCESS_LARGE",
        max_queue_size=2,    # Limited queue for memory-intensive tasks
        concurrency=1,       # Process one at a time to manage resources
        handler=process_large_image,
    ): {
        "THUMBNAIL": lambda _: True,
    },
    State(
        id="THUMBNAIL",
        max_queue_size=5,
        concurrency=2,
        handler=create_thumbnail,
        accumulate_outputs=True,  # Collect final results
        accumulator_max_queue_size=10,
    ): {},
    State(
        id="ERROR",
        max_queue_size=10,
        concurrency=1,
        accumulate_outputs=True,  # Collect errors for reporting
    ): {},
}

# Use the state machine
async with AsyncStateMachine(transition_graph) as machine:
    # Inject some tasks
    tasks = [
        ImageTask(data=b"small1", size=500),
        ImageTask(data=b"small2", size=800),
        ImageTask(data=b"large1", size=2_000_000),
        ImageTask(data=b"", size=100),  # Will trigger error
    ]

    # Create tasks for processing
    for task in tasks:
        await machine.inject(task, "READ")

    # Wait for all tasks to be processed
    await machine.empty_wait()

    # Collect successful results
    async for result in machine.accumulated_values("THUMBNAIL"):
        print(f"Processed image with history: {result.history}")

    # Collect errors
    async for error in machine.accumulated_values("ERROR"):
        print(f"Failed to process image: {error.error}")
```
"""

from __future__ import annotations

import asyncio
import collections
import logging
from beets import logging
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from typing import (
    AsyncGenerator,
    Callable,
    Coroutine,
    Generator,
    Generic,
    TypeVar,
)

from frozendict import frozendict

T = TypeVar("T")

log = logging.getLogger("beets")

StateId = str
StateTaskHandler = Callable[
    [T],
    AsyncGenerator[T, None]
    | Generator[T, None, None]
    | Coroutine[T, None, None]
    | T,
]


class StateQueue(asyncio.Queue[T]):
    """A queue for a state's tasks.

    This class extends asyncio.Queue to provide a queue for a state's tasks.
    """

    def __init__(self, *args, id: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.id = id

    def __str__(self) -> str:
        return f"<StateQueue id={self.id}, {super().__str__()}>"

    def __repr__(self) -> str:
        return f"<StateQueue id={self.id}, {super().__repr__()}>"

@dataclass(frozen=True)
class State(Generic[T]):
    # The identifier for the state
    id: StateId = field(metadata={"validate": lambda x: x and len(x) > 0})

    # The handler for each task that enters this state.
    handler: StateTaskHandler[T] = field(
        metadata={"validate": lambda x: asyncio.iscoroutinefunction(x)}
    )

    # Whether tasks in this state require user interaction, and thus cannot be run
    # in parallel.
    user_interaction: bool = field(default=False)

    # The maximum number of tasks that can be enqueued in this state at any given
    # time. 0 means no limit.
    max_queue_size: int = field(
        default=0, metadata={"validate": lambda x: x >= 0}
    )

    # The number of coroutines that will process the queue's contents concurrently.
    #
    # If zero (the default), then the state machine will use `max_queue_size` to
    # determine its concurrency.
    #
    # If one, then the state machine will process tasks sequentially.
    #
    # Must not be greater than `max_queue_size`.
    # If `max_queue_size` is zero (unbounded capacity), then this must be positive.
    concurrency: int = field(default=0, metadata={"validate": lambda x: x >= 0})

    # Whether to accumulate outputs from this state. If true, the state machine will
    # add all the outputs from this state to the public accumulator queue.
    accumulate: bool = field(default=False)

    # The maximum number of values that can be enqueued in this state's accumulator
    # queue.
    #
    # 0 means no limit.
    max_accumulator_queue_size: int = field(
        default=0, metadata={"validate": lambda x: x >= 0}
    )

    # The queue for the state's tasks - initialized in __post_init__
    _queue: asyncio.Queue[T] = field(init=False)

    # The queue for the state's accumulator - initialized in __post_init__
    _accumulator: asyncio.Queue[T] = field(init=False)

    def __post_init__(self):
        # Use object.__setattr__ to set the queue since the class is frozen
        object.__setattr__(
            self, "_queue", StateQueue(id=f"{self.id}-queue", maxsize=self.max_queue_size)
        )
        object.__setattr__(
            self,
            "_accumulator",
            StateQueue(id=f"{self.id}-accumulator", maxsize=self.max_accumulator_queue_size),
        )

        if self.concurrency > self.max_queue_size:
            raise ValueError(
                f"Concurrency ({self.concurrency}) must not be greater "
                f"than max_queue_size ({self.max_queue_size})"
            )

        if self.max_queue_size == 0 and self.concurrency == 0:
            raise ValueError(
                "max_queue_size and concurrency cannot both be zero"
            )


Condition = Callable[[T], bool]
Transition = tuple[StateId, Condition[T]]
Transitions = tuple[Transition[T], ...]
StateAndTransitions = tuple[State[T], Transitions[T]]
Graph = tuple[StateAndTransitions[T], ...]
_TransitionHandler = Callable[[T], None]


class AsyncStateMachine(AbstractAsyncContextManager, Generic[T]):
    """A generic state machine implementation.

    This class provides a framework for implementing state machines with parallel
    and sequential async state processing capabilities.

    ## Example usage:

    ```python
    transition_graph = { ... }
    async with AsyncStateMachine(transition_graph) as machine:
        await machine.inject(task, "INIT")
        for output in machine.accumulated("END"):
            print(output)
    ```

    ## Defining state transition graph:

    The state transition graph is an immutable sequence of tuples, each joining
    a state with its transitions to other states. Each transition identifies a
    destination state and a conditional which, when true, will cause a state's
    handler's output to be enqueued in the destination state's queue.

    The transitions for a state are evaluated in order, and the first transition
    that evaluates to true will be applied. If no transitions evaluate to true,
    then the handler's output will be discarded. In this case, it's likely that
    the state should be an accumulator, so that the handler's output can be
    retrieved by the state machine's user, but discarding the output is not
    an error condition.

    ## Accumulating outputs:

    Select states can accumulate their outputs, which will be made available through
    the machine's accumulated_values() method. This yields values as they are
    accumulated, and removes them from the internal accumulator queue. To bound
    memory usage, the accumulator queue can be configured with a max size. If this
    is done, the state machine will block when the accumulator queue is full.
    This presents a potential deadlock behavior if the user continues to inject
    inputs past when the accumulator is full, while not consuming the accumulated
    values. To avoid this, if there is a maximum size set for the accumulator,
    then care should be taken to concurrently inject inputs and consume the
    accumulated outputs.

    For example:
    ```python
    transition_graph = {
        State(
            id="START",
            max_queue_size=10,
            handler=lambda x: yield x * 2,  # Multiply inputs by 2
        ): {"END": lambda _: True},
        State(
            id="END",
            max_queue_size=10,
            handler=lambda x: yield x * 3,  # Multiply inputs by 3
            accumulate=True,
            accumulator_max_queue_size=10,
        ): {},
    }
    async with AsyncStateMachine(transition_graph) as sm:
        inject_tasks = []
        for i in range(500):
            inject_tasks.append(asyncio.create_task(sm.inject(i, "START")))

        # Accumulate the outputs in an async task to ensure that the injection
        # tasks can all complete. If we don't consume from the accumulator,
        # which has a maximum size of 10, then the state machine will apply
        # backpressure all the way back to the inject tasks, and they will
        # never complete.
        async def accumulate():
            async for output in sm.accumulated("END"):
                print(output)
        accumulate_task = asyncio.create_task(accumulate())

        await asyncio.gather(*inject_tasks)
        await accumulate_task
    ```

    This will print:
    ```
    > 0
    > 6
    > 12
    > 18
    > 24
    ...
    ```

    ## Order of processing:

    If
     - there are no cycles in the transition graph,
     - all of the state handlers process tasks sequentially, and yield zero or one
       output tasks per inputs,
     - none of the state handlers perform work on other threads, and
     - the state machine accumulates outputs from only one state, then

    the state machine will yield accumulated outputs in the same order as
    its inputs were injected.

    ## Managing concurrency:

    Concurrency in the state machine is configured for each state independently.
    There are two mechanisms for managing a state's processing concurrency:
    - The queue's maximum size, and
    - The number of coroutines that will process the queue's contents concurrently

    Each state maintains a queue of work to process with its state handler method.
    This queue has a maximum size parameter, which by default is 0, meaning the
    queue's maximum capacity is unbounded. If the maximum size is positive, then
    the when the queue reaches that size, it will block new items transitioning to
    the state until there is available capacity.

    The number of coroutines that will process the queue's contents concurrently is
    specified by the state's concurrency parameter. This defaults to 1, meaning
    each state will process its work in only one continuously-running coroutine.

    ## Thread safety:

    The state machine is not thread safe. It maintains the same thread safety
    characteristics as the asyncio.Queue and other async libraries. State machine
    initialization, starting, injecting, accumulating outputs, and joining (and
    use as a context manager) must all be performed from the same thread.

    It is safe for individual state handlers to perform work on other threads,
    as long as the outputs of the handler are yielded on the same thread that
    called the handler method.

    ## Graph cycles:

    The state machine supports graphs with cycles, however it is not possible to
    detect infinite cycles. It is the user's responsibility to ensure that the
    state graph does not contain infinite cycles.

    Type Parameters:
        T: The type of tasks processed by the state machine.
    """

    def __init__(
        self,
        graph: Graph[T],
    ):
        """Initialize the state machine with state definitions.

        Args:
            transition_graph: The state-transition graph definition.
        """
        self._validate_graph(graph)

        # A mapping of state ids to states.
        self._states: tuple[State[T], ...] = tuple(s for s, _ in graph)
        self._states_by_id: dict[StateId, State[T]] = {
            s.id: s for s in self._states
        }
        if not any(s.accumulate for s in self._states):
            log.warning(
                "No states are set to accumulate outputs. This means "
                "that none of the tasks injected will produce output "
                "that will be accessible by the state machine's API. "
                "This may not be what you want, unless you are relying "
                "on the state handlers' side effects."
            )

        self._queues: tuple[asyncio.Queue[T], ...] = tuple(
            s._queue for s in self._states
        )

        # A mapping of states to decorated handler functions. These decorated
        # functions transition all of the handler's outputs to the appropriate
        # next state, and add them to the state's accumulator queue if the state
        # is so configured.
        #
        # These are the methods that should be called to process the tasks in
        # the state's queue.
        self._decorated_handle_fns: dict[State, _TransitionHandler[T]] = {
            state: self._handle_and_transition_fn(state) for state, _ in graph
        }

        # A mapping of states to the transition conditionals, which determine
        # which state an output of a state's handler should transition to.
        self._transitions: dict[State[T], Transitions[T]] = {
            s: transitions for s, transitions in graph
        }

        # Tasks that are processing the state machine's queues. Populated in
        # start(). Cancelled and cleared in join().
        self._processor_tasks: list[asyncio.Task[None]] = []

    def _validate_graph(self, graph: Graph[T]):
        if len(graph) == 0:
            raise ValueError("Transition graph must contain at least one state")

        # Verify that no two states have the same id
        state_ids = collections.Counter(s.id for s, _ in graph)
        nonunique_ids = tuple(
            id for id, count in state_ids.items() if count > 1
        )
        if nonunique_ids:
            raise ValueError(
                f"Duplicate state IDs found in transition graph: {nonunique_ids}"
            )

        # Verify that all transitions reference valid state IDs
        for state, transitions in graph:
            transition_state_ids = set(id for id, _ in transitions)
            for id in transition_state_ids:
                if id not in state_ids:
                    raise ValueError(
                        f"Invalid transition in state {state.id}: "
                        f"transitions to non-existent state '{id}'"
                    )

    def _handle_and_transition_fn(
        self, state: State[T]
    ) -> _TransitionHandler[T]:
        """Decorate a state's handler function to transition and accumulate outputs.

        Args:
            from_state: The name of the state this handler belongs to.
            handler: The handler function to decorate.

        Returns:
            A function that wraps the handler function.
        """

        async def transition(trepr: str, ptask: T) -> None:
            next_state = self._next_state(ptask, self._transitions[state])
            prepr = str(ptask)
            if next_state:
                log.debug(
                    "{0:s}: {1:s} -> {2:s} -> {3:s}",
                    state.id,
                    trepr,
                    prepr,
                    next_state.id,
                )
                await next_state._queue.put(ptask)

            if state.accumulate:
                log.debug(
                    "{0:s}: {1:s} -> {2:s} -> accumulator",
                    state.id,
                    trepr,
                    prepr,
                )
                await state._accumulator.put(ptask)

            if not next_state and not state.accumulate:
                log.debug(
                    "{0:s}: {1:s} -> {2:s} -> terminal",
                    state.id,
                    trepr,
                    prepr,
                )

        async def wrapped(task: T) -> None:
            trepr = str(task)

            processed = state.handler(task)
            if isinstance(processed, AsyncGenerator):
                async for ptask in processed:
                    await transition(trepr, ptask)
            elif isinstance(processed, Generator):
                for ptask in processed:
                    await transition(trepr, ptask)
            elif isinstance(processed, Coroutine):
                await transition(trepr, await processed)
            else:
                await transition(trepr, processed)

        return wrapped

    def _next_state(
        self, task: T, transitions: Transitions[T]
    ) -> State[T] | None:
        """Determine the next state based on the transition graph.

        Args:
            task: The current task.
            from_state: The current state.

        Returns:
            The next state to transition to, or None if the current state is terminal.

        Raises:
            ValueError: If the state is not terminal and no valid transitions are found.
        """
        if not transitions:
            # Reached a terminal state.
            return None

        # Process the transitions in order, and return the state id of the first
        # valid transition.
        for next_state_id, condition in transitions:
            if condition(task):
                return self._states_by_id[next_state_id]

        # No valid transitions is an error state. This task should not transition
        # to any other state.
        return None

    async def _process_state_queue(self, state: State[T]):
        """Process tasks in this state's queue."""
        log.debug("{0:s}: starting processor", state.id)
        queue = state._queue
        handler = self._decorated_handle_fns[state]
        while True:
            try:
                task = await queue.get()
            except asyncio.exceptions.CancelledError:
                return

            try:
                await handler(task)
            except asyncio.exceptions.CancelledError:
                log.debug("{0:s}: task {1:s} cancelled", state.id, task)
                return
            except Exception as e:
                log.exception(
                    "{0:s}: error processing task {1:s}: {2:s}",
                    state.id,
                    str(task),
                    str(e),
                    exc_info=True,
                )
                raise
            finally:
                queue.task_done()

    def _n_processors(self, state: State[T]) -> int:
        """Determine the number of processors to use for a state.

        Args:
            state: The state to determine the number of processors for.

        Returns:
            The number of processors to use for the state.
        """
        return state.concurrency or state.max_queue_size

    def start(self) -> None:
        """Start the state machine.

        Initializes and starts processing coroutines for each state.
        """
        assert not self._processor_tasks, "State machine already started"

        log.debug("Starting state machine")
        self._processor_tasks = [
            asyncio.create_task(
                self._process_state_queue(state),
                name=f"StateProcessor-{state.id}-{i}",
            )
            for state in self._states
            for i in range(self._n_processors(state))
        ]
        log.debug("Started {0:d} processor tasks", len(self._processor_tasks))

    async def inject(self, task: T, state_id: StateId) -> None:
        """Inject a task into the state machine, and wait for it to be enqueued.

        Note that the state machine should have been started before tasks are injected,
        as the queue the task is injected into may already be at capacity. If this is
        the case, and the state machine is not running, the queue's existing tasks will
        not be processed, and this will block forever.

        Args:
            task: The task to inject.
            state_id: The state to inject the task into.
        """
        log.debug("Injector: {0:s} -> {1:s}", str(task), state_id)
        state = self._states_by_id[state_id]
        await state._queue.put(task)

    async def accumulated(self, state_id: StateId) -> AsyncGenerator[T, None]:
        """Get and remove a value from the accumulator queue.

        Internally, this relies on getting a value from an asyncio.Queue, which
        has a maximum size. If this queue reaches capacity, the state machine will
        block waiting for the accumulator to be emptied.

        Yields:
            A value from the accumulator queue.
        """
        assert state_id in self._states_by_id, f"State '{state_id}' not found"
        state = self._states_by_id[state_id]

        assert (
            state.accumulate
        ), f"State '{state.id}' does not accumulate outputs"
        accumulator = state._accumulator

        # Iterate until both the state machine is empty and the accumulator is
        # empty. Until the state machine is empty, it remains possible for
        # new values to be added to the accumulator.
        while not (self.empty() and accumulator.empty()):
            if not accumulator.empty():
                value = await accumulator.get()
                accumulator.task_done()
                log.debug("{0:s}: accumulator -> {1:s}", state.id, str(value))
                yield value
            else:
                await asyncio.sleep(0.1)

    def _log_state(self):
        """Log the current status of the state machine."""
        if log.isEnabledFor(logging.DEBUG):
            log.debug("State machine state:")
            for s in self._states:
                log.debug(
                    "\t{0:s}\tqueue: {1:d}/{2:s}, accumulator: {3:d}/{4:s}",
                    s.id,
                    s._queue.qsize(),
                    s.max_queue_size or "∞",
                    s._accumulator.qsize(),
                    s.accumulator_max_queue_size or "∞",
                )

    def empty(self) -> bool:
        """Check if the state machine is empty - that all tasks are completed.

        Returns:
            True if the state machine is empty, False otherwise.
        """
        return all(q.empty() for q in self._queues)

    async def empty_wait(self) -> None:
        """Wait until the state machine is empty."""
        while not self.empty():
            await asyncio.gather(*(q.join() for q in self._queues))

    async def join(self) -> None:
        """Wait for the state machine to finish, then reset the state machine."""
        # Wait for all queues to be empty and all tasks to be processed
        log.debug("Waiting for state machine to finish")
        try:
            await self.empty_wait()
        except asyncio.exceptions.CancelledError:
            log.debug("State machine cancelled.")
        finally:
            log.debug("Cancelling all processor tasks.")
            for task in self._processor_tasks:
                task.cancel()
            await asyncio.gather(*self._processor_tasks)
            self._processor_tasks = []
            log.debug(
                "All work cancelled and completed. State machine is reset."
            )

    async def __aenter__(self):
        """Enter the async context manager."""
        self.start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Exit the async context manager."""
        del exc_type, exc_value, traceback
        await self.join()
