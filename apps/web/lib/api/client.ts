const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const DEMO_USER_ID = process.env.NEXT_PUBLIC_DEMO_USER ?? "demo-user";

interface ApiErrorBody {
  detail?: unknown;
  error?: {
    code?: string;
    message?: string;
  };
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function messageFromBody(rawBody: string, status: number): string {
  try {
    const payload = JSON.parse(rawBody) as ApiErrorBody;
    if (typeof payload.detail === "string" && payload.detail.trim()) {
      return payload.detail;
    }
    if (payload.error?.message) {
      return payload.error.message;
    }
  } catch {
    if (rawBody.trim()) {
      return rawBody.trim();
    }
  }
  return `Request failed (${status})`;
}

export async function apiFetch<T>(
  path: string,
  token: string,
  init?: Omit<RequestInit, "headers"> & { headers?: HeadersInit },
): Promise<T> {
  const authHeaders: HeadersInit =
    token.trim().length > 0
      ? { Authorization: `Bearer ${token}` }
      : { "x-demo-user": DEMO_USER_ID };
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      ...authHeaders,
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!response.ok) {
    const rawBody = await response.text();
    throw new ApiError(response.status, messageFromBody(rawBody, response.status));
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export function uploadWithProgress(
  url: string,
  file: File,
  onProgress: (percent: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable || event.total === 0) {
        return;
      }
      onProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        onProgress(100);
        resolve();
        return;
      }
      reject(new ApiError(xhr.status, `Upload failed (${xhr.status})`));
    };
    xhr.onerror = () => reject(new ApiError(0, "Upload failed before the file reached storage."));
    xhr.send(file);
  });
}
