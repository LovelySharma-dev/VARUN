import { BadRequestException } from '@nestjs/common';
import { ZodType } from 'zod';

export function validateResponse<T>(
  schema: ZodType<T>,
  data: unknown,
): T {
  const result = schema.safeParse(data);

  if (!result.success) {
    throw new BadRequestException({
      error: {
        code: 'CONTRACT_VALIDATION_FAILED',
        message: 'API response does not match its contract.',
        retryable: false,
        details: result.error.issues,
      },
    });
  }

  return result.data;
}
