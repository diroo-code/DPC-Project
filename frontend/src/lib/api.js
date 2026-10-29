// Thin API client. One place that knows about tokens, error shapes and status codes.

const BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(status, message, body) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

let tokenProvider = () => null;

export function setTokenProvider(fn) {
  tokenProvider = fn;
}

function authHeaders() {
  const token = tokenProvider();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function request(path, options = {}) {
  const { method = "GET", body, formData, signal } = options;
  const headers = { ...authHeaders() };
  let payload;

  if (formData) {
    payload = formData;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(`${BASE}${path}`, { method, headers, body: payload, signal });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new ApiError(0, "Could not reach the server. Check that the backend is running.");
  }

  if (response.status === 204) return null;

  const text = await response.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }

  if (!response.ok) {
    let detail = data;
    if (data && typeof data === "object") {
      detail = data.detail ?? data.message ?? data.error;
      // FastAPI validation errors arrive as a list of objects.
      if (Array.isArray(detail)) {
        detail = detail
          .map((item) => item.msg || item.message || "Invalid value")
          .join(", ");
      }
    }
    const message =
      typeof detail === "string" && detail
        ? detail
        : response.status === 401
          ? "Your session has expired. Please sign in again."
          : `Request failed with status ${response.status}.`;
    throw new ApiError(response.status, message, data);
  }

  return data;
}

// ------------------------------------------------------------------ auth and profiles

export const getMe = () => request("/api/v1/auth/me");

// Signed URLs come back relative to the API host. The browser needs an absolute path when the
// frontend is served from a different origin.
export function mediaUrl(path) {
  if (!path) return path;
  if (/^https?:\/\//i.test(path)) return path;
  return `${BASE}${path}`;
}
export const updateMe = (payload) => request("/api/v1/auth/me", { method: "PATCH", body: payload });
export const getProfile = (id) => request(`/api/v1/profiles/${id}`);

// ------------------------------------------------------------------ photos

export function listPhotos({ limit = 12, offset = 0, uploader, tag, dateFrom, dateTo } = {}) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (uploader) params.set("uploader", uploader);
  if (tag) params.set("tag", tag);
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  return request(`/api/v1/photos?${params}`);
}

export function searchPhotos({ q, limit = 12, offset = 0, uploader, tag, dateFrom, dateTo }) {
  const params = new URLSearchParams({ q, limit: String(limit), offset: String(offset) });
  if (uploader) params.set("uploader", uploader);
  if (tag) params.set("tag", tag);
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  return request(`/api/v1/photos/search?${params}`);
}

export const getPhoto = (id) => request(`/api/v1/photos/${id}`);
export const photoUrl = (id) => request(`/api/v1/photos/${id}/url`);
export const deletePhoto = (id) => request(`/api/v1/photos/${id}`, { method: "DELETE" });
export const replaceTags = (id, tags) =>
  request(`/api/v1/photos/${id}/tags`, { method: "PUT", body: { tags } });

export function uploadPhoto({ file, caption, visibility, tags, signal }) {
  const form = new FormData();
  form.append("file", file);
  if (caption) form.append("caption", caption);
  form.append("visibility", visibility);
  if (tags) form.append("tags", tags);
  return request("/api/v1/photos", { method: "POST", formData: form, signal });
}

// ------------------------------------------------------------------ comments

export const listComments = (photoId) => request(`/api/v1/photos/${photoId}/comments`);
export const addComment = (photoId, body) =>
  request(`/api/v1/photos/${photoId}/comments`, { method: "POST", body: { body } });
export const deleteComment = (commentId) =>
  request(`/api/v1/comments/${commentId}`, { method: "DELETE" });

// ------------------------------------------------------------------ friends

export const listFriends = () => request("/api/v1/friends");
export const listFriendRequests = () => request("/api/v1/friends/requests");
export const sendFriendRequest = (username) =>
  request("/api/v1/friends/requests", { method: "POST", body: { username } });
export const acceptFriendRequest = (id) =>
  request(`/api/v1/friends/requests/${id}/accept`, { method: "POST" });
export const rejectFriendRequest = (id) =>
  request(`/api/v1/friends/requests/${id}/reject`, { method: "POST" });
export const removeFriend = (id) => request(`/api/v1/friends/${id}`, { method: "DELETE" });
