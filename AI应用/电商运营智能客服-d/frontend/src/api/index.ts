import axios from 'axios';
import type { UserInfo, Session, ChatOutput, HistoryMessage, KbFileListResponse, KbFileDetailResponse } from '../types';

const api = axios.create({ baseURL: '/api' });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) { localStorage.clear(); window.location.href = '/'; }
    return Promise.reject(err);
  }
);

export const registerUser = (data: { username: string; password: string }) =>
  api.post<{ access_token: string }>('/register', data);

export const loginUser = (username: string, password: string) => {
  const fd = new FormData(); fd.append('username', username); fd.append('password', password);
  return api.post<{ access_token: string }>('/token', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
};

export const getMe = () => api.get<UserInfo>('/me');

export const getSessions = () => api.get<Session[]>('/sessions');

export const sendMessage = (message: string, sessionId: string) =>
  api.post<ChatOutput>('/chat', { message, session_id: sessionId });

export const getHistory = (sessionId: string) =>
  api.get<{ messages: HistoryMessage[] }>(`/history/${sessionId}`);

export const renameSession = (sessionId: string, title: string) =>
  api.put<{ status: string; title: string }>(`/sessions/${sessionId}/rename`, { title });

export const deleteSession = (sessionId: string) =>
  api.delete<{ status: string }>(`/sessions/${sessionId}`);

export const sendMessageStream = (
  message: string,
  sessionId: string,
  onToken: (token: string) => void,
  onDone: (intent: string, aiResponse: { type: string; content: string }) => void,
  onError: (err: string) => void,
) => {
  const token = localStorage.getItem('token');
  fetch('/api/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ message, session_id: sessionId }),
  }).then(async (res) => {
    if (!res.ok) { onError(`HTTP ${res.status}`); return; }
    const reader = res.body?.getReader();
    if (!reader) { onError('No body'); return; }
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const event = JSON.parse(line.slice(6));
            if (event.type === 'token') onToken(event.content);
            else if (event.type === 'done') onDone(event.intent, event.ai_response);
          } catch {}
        }
      }
    }
  }).catch(() => onError('网络错误'));
};

export const getKbFiles = (page = 1, pageSize = 10) =>
  api.get<KbFileListResponse>(`/kb/files?page=${page}&page_size=${pageSize}`);

export const getKbFileDetail = (fileId: number) =>
  api.get<KbFileDetailResponse>(`/kb/files/${fileId}`);

export const deleteKbFile = (fileId: number) =>
  api.delete<{ status: string; chunks_removed: number }>(`/kb/files/${fileId}`);

export const deleteKbChunk = (chunkId: string) =>
  api.delete<{ status: string }>(`/kb/chunks/${chunkId}`);