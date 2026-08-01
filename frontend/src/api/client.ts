import type {
  BookStatusResponse,
  BookSummary,
  BookUploadResponse,
  ChatMessageResponse,
  ChatResponse,
  ChunkContentResponse,
  ChunkSummary,
  ProfileResponse,
  ProfileUpdateRequest,
} from './types'

const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export interface HealthResponse {
  status: string
  environment: string
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init)
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.detail ?? `Request to ${path} failed: ${response.status}`)
  }
  return response.json()
}

export async function getHealth(): Promise<HealthResponse> {
  return request('/health')
}

export async function listBooks(): Promise<BookSummary[]> {
  return request('/books')
}

export async function uploadBook(file: File, title?: string): Promise<BookUploadResponse> {
  const formData = new FormData()
  formData.append('file', file)
  if (title) formData.append('title', title)
  return request('/books', { method: 'POST', body: formData })
}

export async function getBookStatus(bookId: string): Promise<BookStatusResponse> {
  return request(`/books/${bookId}/status`)
}

export async function listBookChunks(bookId: string): Promise<ChunkSummary[]> {
  return request(`/books/${bookId}/chunks`)
}

export async function getChunkContent(chunkId: string): Promise<ChunkContentResponse> {
  return request(`/chunks/${chunkId}/content`)
}

export async function getChunkChatHistory(chunkId: string): Promise<ChatMessageResponse[]> {
  return request(`/chunks/${chunkId}/chat`)
}

export async function askChunk(chunkId: string, question: string): Promise<ChatResponse> {
  return request(`/chunks/${chunkId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })
}

export async function getProfile(): Promise<ProfileResponse> {
  return request('/profile')
}

export async function updateProfile(update: ProfileUpdateRequest): Promise<ProfileResponse> {
  return request('/profile', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(update),
  })
}
