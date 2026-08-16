const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ??
  "http://localhost:8001";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    credentials: "include",
    headers:
      init.body instanceof FormData
        ? init.headers
        : { "Content-Type": "application/json", ...init.headers },
  });
  if (!response.ok) {
    let message = "요청을 처리하지 못했습니다.";
    try {
      const payload = await response.json();
      message =
        typeof payload.detail === "string"
          ? payload.detail
          : payload.detail?.[0]?.msg ?? message;
    } catch {
      // Keep the user-facing fallback for non-JSON errors.
    }
    throw new ApiError(response.status, message);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function downloadExport(
  recordId: string,
  packageIds: string[],
): Promise<void> {
  const response = await fetch(`${API_URL}/api/records/${recordId}/export`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ package_ids: packageIds }),
  });
  if (!response.ok) {
    const payload = await response.json();
    throw new ApiError(response.status, payload.detail ?? "ZIP을 만들지 못했습니다.");
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `storilog-${recordId.slice(0, 8)}.zip`;
  link.click();
  URL.revokeObjectURL(url);
}
