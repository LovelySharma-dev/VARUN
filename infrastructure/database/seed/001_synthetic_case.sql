BEGIN;

-- Synthetic-only smoke fixture. It is not a real incident and must never be
-- reported as model accuracy or legal vessel attribution.
INSERT INTO cases (case_id, case_code, title, description, data_origin, region)
VALUES (
  '00000000-0000-4000-8000-000000000001',
  'SYN-DEMO-001',
  'Controlled synthetic SIH smoke case',
  'Known geometry/time fixture for contract, PostGIS and privacy tests.',
  'SYNTHETIC',
  ST_GeomFromText('POLYGON((72.70 18.80,72.95 18.80,72.95 19.00,72.70 19.00,72.70 18.80))',4326)
)
ON CONFLICT (case_code) DO NOTHING;

INSERT INTO scenes (
  scene_id, case_id, external_scene_id, sensor, acquisition_time_utc,
  footprint, crs, data_origin, metadata
)
VALUES (
  '00000000-0000-4000-8000-000000000002',
  '00000000-0000-4000-8000-000000000001',
  'SYN-SAR-SCENE-001',
  'SYNTHETIC_SAR',
  '2026-08-20T05:30:00Z',
  ST_GeomFromText('POLYGON((72.72 18.82,72.93 18.82,72.93 18.98,72.72 18.98,72.72 18.82))',4326),
  'EPSG:4326',
  'SYNTHETIC',
  '{"fixturePurpose":"coordinate-time-contract-smoke"}'::jsonb
)
ON CONFLICT (case_id, external_scene_id) DO NOTHING;

COMMIT;
