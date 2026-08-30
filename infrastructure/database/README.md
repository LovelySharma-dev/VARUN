# Database

PostgreSQL/PostGIS schema ownership, migrations, indexes and seed fixtures. Use one migration owner; restrict the Phase 3 identity map and audit authorised access.

Start with:

- `docs/DATABASE-DESIGN.md` - full entities, relationships and rules.
- `docs/DATABASE-EASY-GUIDE.md` - beginner-friendly explanation.
- `migrations/001_initial_schema.sql` - canonical schema.
- `migrations/002_roles_and_privacy.sql` - privacy/ground-truth separation.
- `seed/001_synthetic_case.sql` - explicitly synthetic smoke fixture.
- `TESTING.md` - local PASS gates.

Prisma mapping is under `apps/api/prisma`; reviewed SQL migrations remain canonical.
