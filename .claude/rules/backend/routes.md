---
paths: [backend/app/api/routes/**/*.py]
---

# Route Rules

Routes are thin. Their only job is to accept a request, call a service, and return a response.

## Must

- Accept input, call one service method, return response
- Validate input via Pydantic models
- Inject all dependencies via `Depends()` — never instantiate anything here
- Use `CurrentUser` dependency for auth
- Return correct status codes: 201 create, 204 delete
- Catch domain exceptions and convert to `HTTPException`

## Must Not

- Contain business logic
- Call repositories directly — routes talk to services only
- Instantiate services, repositories, or clients
- Exceed ~40 lines

## Domain Exception → HTTP Mapping

| Exception             | HTTP    |
| --------------------- | ------- |
| `EntityNotFoundError` | 404     |
| `ValidationError`     | 400/422 |
| `DatabaseError`       | 500     |

```python
# YES
@router.post("/api/items", status_code=201, response_model=ItemResponse)
async def create_item(
    payload: CreateItemRequest,
    user: User = Depends(get_current_user),
    item_service: ItemService = Depends(get_item_service),
) -> ItemResponse:
    return await item_service.create(user_id=user.id, payload=payload)

# NO — route calling a repository directly
@router.post("/api/items", status_code=201)
async def create_item(
    payload: CreateItemRequest,
    item_repo: ItemRepository = Depends(get_item_repo),  # violation
) -> ItemResponse:
    return await item_repo.create(payload)  # violation
```
