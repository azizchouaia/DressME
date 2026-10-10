"""Every agent inherits from BaseAgent. The orchestrator only knows this interface."""

from abc import ABC, abstractmethod
from typing import ClassVar, Generic, TypeVar

from pydantic import BaseModel

In = TypeVar("In", bound=BaseModel)
Out = TypeVar("Out", bound=BaseModel)


class AgentError(Exception):
    """Raise when the agent cannot answer (bad input, model failure...)."""


class BaseAgent(ABC, Generic[In, Out]):
    name: ClassVar[str]
    description: ClassVar[str]          # read by the orchestrator LLM to choose the tool
    input_model: ClassVar[type[BaseModel]]
    output_model: ClassVar[type[BaseModel]]
    is_async_job: ClassVar[bool] = False  # True -> heavy work goes to the Celery worker

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    async def setup(self) -> None:
        """Load models / clients once at startup. Override if needed."""

    @abstractmethod
    async def run(self, inp: In) -> Out:
        """Main entry point: validated input -> validated output."""

    async def __call__(self, payload: dict) -> dict:
        inp = self.input_model.model_validate(payload)
        out = await self.run(inp)
        return self.output_model.model_validate(out).model_dump(mode="json")

    def health(self) -> dict:
        return {"agent": self.name, "status": "ok"}
