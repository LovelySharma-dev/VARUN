# apps/api

NestJS public gateway, PostgreSQL/PostGIS persistence and pg-boss workers. Owns run creation/status, canonical validation, privacy-safe candidateId projection, complete-dashboard composition, retries and cancellation. Browser clients never call Python engines directly.

Database mapping is in `prisma/schema.prisma`; reviewed PostGIS SQL migrations remain canonical under `infrastructure/database`.
