import { z } from 'zod';

export const TestRunResponseSchema = z.object({
  runId: z.string().uuid(),
  status: z.enum(['QUEUED', 'RUNNING', 'COMPLETED', 'FAILED']),
  progress: z.number().int().min(0).max(100),
  createdAt: z.string().datetime(),
  startedAt: z.string().datetime().optional(),
  completedAt: z.string().datetime().optional(),
  error: z.string().optional(),
});

export const CaseSchema = z.object({
  caseId: z.string().uuid(),
  status: z.string(),
  dataOrigin: z.string(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime(),
  metadata: z.record(z.string(), z.unknown()),
});

export const SceneSchema = z.object({
  sceneId: z.string().uuid(),
  caseId: z.string().uuid(),
  externalSceneId: z.string(),
  sensor: z.string(),
  acquisitionTimeUtc: z.string().datetime(),
  crs: z.string(),
  dataOrigin: z.string(),
  metadata: z.record(z.string(), z.unknown()),
});

export const CasesResponseSchema = z.object({
  cases: z.array(CaseSchema),
});

export const ScenesResponseSchema = z.object({
  scenes: z.array(SceneSchema),
});

export type TestRunResponse = z.infer<typeof TestRunResponseSchema>;
export type CaseResponse = z.infer<typeof CaseSchema>;
export type SceneResponse = z.infer<typeof SceneSchema>;
