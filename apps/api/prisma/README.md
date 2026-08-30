# Prisma and PostGIS boundary

`schema.prisma` maps ordinary CRUD and relations. The canonical database definition is the ordered SQL migration set under `infrastructure/database/migrations` because PostGIS geometry types, GiST indexes, views, checks and privacy grants require SQL.

Do not run `prisma db push` against shared/demo databases. Apply reviewed SQL migrations, then run `prisma generate`. Use parameterized `pg` repositories for spatial queries.
