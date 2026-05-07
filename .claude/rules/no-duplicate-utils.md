# No Duplicate Utils

Before writing any helper function, check whether the functionality already
exists in the utils layer.

**Backend:** Search `backend/app/utils/` before adding any helper to a service,
repository, or route. If the logic is pure (no side effects, no DB, no API calls),
it belongs in utils — not inline in the service that first needs it.

**Frontend:** Search `frontend/src/lib/utils/` before adding any helper to a
component, store, or server action.

If you find an existing utility that's close but not quite right, extend it or
add an overload rather than creating a parallel implementation. If nothing exists,
create the util first, then use it from the calling code.
