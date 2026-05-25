from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ActionResult:
    success: bool
    message: str
    data: Optional[Any] = None
    errors: list[str] = field(default_factory=list)

    @classmethod
    def ok(cls, message: str, data: Optional[Any] = None) -> "ActionResult":
        return cls(success=True, message=message, data=data)

    @classmethod
    def fail(
        cls,
        message: str,
        *,
        errors: Optional[list[str]] = None,
        data: Optional[Any] = None,
    ) -> "ActionResult":
        return cls(success=False, message=message, data=data, errors=errors or [])
