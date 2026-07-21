export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly requestId?: string,
    public readonly retryAfterSeconds?: number,
    public readonly category:
      | "network"
      | "timeout"
      | "rate-limit"
      | "server"
      | "validation"
      | "unknown" = "unknown",
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Mayabu could not complete this request.";
}
