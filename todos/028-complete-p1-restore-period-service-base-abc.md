---
status: pending
priority: p1
issue_id: "028"
tags: [code-review, architecture, backend, abc]
dependencies: []
---

# `PeriodServiceBase` ABC was deleted — violates mandatory project convention

## Problem Statement

`period_base.py` was deleted in this branch (originally created, then removed). CLAUDE.md explicitly requires: "Always use ABC (Abstract Base Class), not Protocol. Define in `[service_name]_base.py`." Without it, `get_period_service` in `dependencies.py` returns the concrete class, breaking the interface seam used for testing and future provider swapping.

## Findings

- **File**: `backend/app/services/period_base.py` — deleted (`D` in git status)
- Prior todo 009 incorrectly labeled this "YAGNI" — ABCs are a mandatory pattern per CLAUDE.md
- Every other service with meaningful logic (`LLMProvider`) follows this convention

## Proposed Solution

Restore `backend/app/services/period_base.py`:
```python
from abc import ABC, abstractmethod
from typing import Optional
from app.models.period import (
    CreatePeriodLogResponse, PeriodLogCreate, PeriodLogListResponse,
    PeriodLogResponse, PeriodLogUpdate, CycleAnalysisResponse
)

class PeriodServiceBase(ABC):
    @abstractmethod
    async def create_log(self, user_id: str, data: PeriodLogCreate) -> CreatePeriodLogResponse: ...
    @abstractmethod
    async def get_logs(self, user_id: str, start_date=None, end_date=None) -> PeriodLogListResponse: ...
    @abstractmethod
    async def update_log(self, user_id: str, log_id: str, data: PeriodLogUpdate) -> PeriodLogResponse: ...
    @abstractmethod
    async def delete_log(self, user_id: str, log_id: str) -> None: ...
    @abstractmethod
    async def get_analysis(self, user_id: str) -> CycleAnalysisResponse: ...
```

Update `PeriodService(PeriodServiceBase)` and annotate `get_period_service() -> PeriodServiceBase`.

## Acceptance Criteria
- [ ] `period_base.py` exists with ABC defining all public methods
- [ ] `PeriodService` inherits from `PeriodServiceBase`
- [ ] `get_period_service` return type annotated as `PeriodServiceBase`
- [ ] Also update todo 009 to reflect this (mark 009 complete as "decided to keep")
