# Repository overview

- Run Django commands from `house/`, where `manage.py` lives. The Python project package is `house/`, and the main application package is `tennants/` (the misspelled name is part of the Django app and URL configuration).
- This is a Django 5 + Django REST Framework application with server-rendered HTML and JSON API surfaces. It uses SQLite by default in `house/house/settings.py`; Redis is optional, and the configured cache is currently LocMemCache.
- The primary data model is landlord-owned properties: `FlatBuilding -> House -> Tenant -> RentCharge -> Payment`. User ownership is stored on the records with `user = ForeignKey(User, ...)`.
- The secondary Vite/React app lives in `house/tennants/`; its source uses React 18, TypeScript, Vite, Tailwind, shadcn/ui, and TanStack Query.

# Build, test, and lint

## Django

```bash
cd house
python manage.py migrate
python manage.py runserver
python manage.py check
python manage.py makemigrations --check --dry-run
```

The test suite is Django `TestCase`/`APITestCase` code under `tennants/tests/`.

```bash
# Full suite
python manage.py test tennants

# One test module
python manage.py test tennants.tests.test_model_tenant

# One test case
python manage.py test tennants.tests.test_model_tenant.TenantModelTest

# One test method
python manage.py test tennants.tests.test_model_tenant.TenantModelTest.test_tenant_creation
```

No Django linter or formatter configuration is present.

## React/Vite frontend

Run frontend commands from `house/tennants/`:

```bash
npm install
npm run dev
npm run build
npm run lint
npm run preview
```

## Load testing

`house/locustfile.py` contains the Locust scenarios:

```bash
cd house
locust -f locustfile.py --host http://localhost:8000
```

# Architecture

- `house/house/settings.py` defines apps, authentication, JWT, CORS, cache, Twilio, timezone (`Africa/Nairobi`), static/media paths, and SQLite.
- `house/house/urls.py` owns project-level routes. `house/tennants/urls.py` owns the app's API and server-rendered routes and is included under `/api/`; keep route changes synchronized with both URL modules when moving or renaming an endpoint.
- `tennants/models.py` contains property, tenant, rent-charge, payment, reconciliation, SMS, and landlord-profile models.
- `tennants/views/web.py` contains login-protected class-based and function-based HTML views. `tennants/views/api.py` contains DRF list/detail endpoints. `tennants/serializers.py` maps API models and relation ownership rules.
- `tennants/services/reconcile.py` parses uploaded bank statements and matches transactions to tenants. `tennants/services/metrics.py` contains landlord-scoped reporting queries.
- `tennants/signals.py` updates house occupation, invalidates cache, creates auth tokens, records immutable payment history, and sends best-effort SMS notifications.
- `tennants/templates/` contains Django templates. Metrics use partial templates for cards and partials-prefixed includes.
- `tennants/admin.py` provides the Django/Unfold admin registration and customized admin views.

# Code conventions

- Scope every landlord-facing queryset to `request.user`; API and web querysets must not expose another user's buildings, houses, tenants, charges, or payments. Serializer relation fields should also be limited to the current owner.
- Use the existing web/API mixins instead of duplicating ownership and cache behavior:
  - `OwnedQuerysetMixin`, `FormSaveMixin`, and `ProtectedDeleteMixin` in `views/web.py`
  - `ApiViewMixin` in `views/api.py`
- Protect financial relationships with `on_delete=PROTECT`. A flat building or house may not be deleted when it would remove dependent records; expose deactivation or friendly conflicts instead.
- Preserve append-only ledger behavior. `Payment` and `HistoryReport` reject updates and deletes and `Payment.save()` compares locked fields. When a payment is wrong, use a correcting entry rather than editing or deleting it.
- Model classes call `full_clean()` or equivalent validation in `save()`; preserve model validation for occupancy, rent-charge chronology, building capacity, and tenant/charge consistency instead of relying only on forms or serializers.
- Rent charges are unique per tenant/year/month and `amount_due` must match the tenant house's current rent. Payments must belong to the same tenant as their rent charge.
- Keep SMS sending best-effort: provider failures must log and continue rather than rolling back saves or crashing the save signal. Twilio configuration is read through environment variables.
- Cache invalidation is user/prefix aware in the DRF API; use the existing version-key helpers when changing cached list data.
- Django templates for generated deliverables belong under `public/django-templates/`, matching the existing Django template tree, rather than elsewhere in the frontend tree.
