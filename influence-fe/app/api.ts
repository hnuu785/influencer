const API_URL = "";

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

type UploadPreparation = {
  mode: "multipart" | "s3";
  uploads: Array<{
    upload_url: string;
    upload_token: string;
    headers: Record<string, string>;
  }>;
};

export async function uploadMediaFiles(
  files: File[],
): Promise<{ mode: "multipart" | "s3"; uploadTokens: string[] }> {
  if (files.length === 0) return { mode: "multipart", uploadTokens: [] };
  const preparation = await api<UploadPreparation>("/api/uploads/prepare", {
    method: "POST",
    body: JSON.stringify({
      files: files.map((file) => ({
        filename: file.name,
        content_type: file.type,
        size_bytes: file.size,
      })),
    }),
  });
  if (preparation.mode === "multipart") {
    return { mode: "multipart", uploadTokens: [] };
  }
  if (preparation.uploads.length !== files.length) {
    throw new ApiError(502, "업로드 준비 결과를 확인할 수 없습니다.");
  }
  await Promise.all(
    preparation.uploads.map(async (prepared, index) => {
      const response = await fetch(prepared.upload_url, {
        method: "PUT",
        headers: prepared.headers,
        body: files[index],
      });
      if (!response.ok) {
        throw new ApiError(
          response.status,
          `${files[index].name} 업로드에 실패했습니다. 다시 시도해 주세요.`,
        );
      }
    }),
  );
  return {
    mode: "s3",
    uploadTokens: preparation.uploads.map((item) => item.upload_token),
  };
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
