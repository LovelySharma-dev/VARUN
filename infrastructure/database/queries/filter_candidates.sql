-- Parameters:
-- $1 ais_ingest_id, $2 release_start, $3 release_end,
-- $4 GeoJSON search geometry, $5 spatial buffer metres.
-- Buffer is applied here exactly once using geography distance.
SELECT DISTINCT s.identity_id
FROM ais_track_segments s
WHERE s.ais_ingest_id = $1::uuid
  AND tstzrange(s.started_at, s.ended_at, '[]') && tstzrange($2::timestamptz, $3::timestamptz, '[]')
  AND ST_DWithin(
    s.track::geography,
    ST_SetSRID(ST_GeomFromGeoJSON($4),4326)::geography,
    $5::double precision
  );
