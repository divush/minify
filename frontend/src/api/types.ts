// Mirrors backend/src/minify/api/schemas.py exactly. Kept as plain interfaces,
// not shared code with the backend (design.md's frontend/backend separation) —
// just the same shapes, defined twice.

export type Status = 'queued' | 'processing' | 'awaiting_confirmation' | 'ready' | 'failed'

export interface BookUploadResponse {
  book_id: string
  status: Status
}

export interface BookStatusResponse {
  book_id: string
  status: Status
  total_chunks: number
  ready_chunks: number
}

export interface BookSummary {
  id: string
  title: string | null
  source_filename: string
  status: Status
  total_chunks: number
  ready_chunks: number
}

export interface ChunkSummary {
  id: string
  index: number
  heading: string | null
  page_start: number
  page_end: number
  status: Status
}

export interface ChunkContentResponse {
  id: string
  index: number
  heading: string | null
  page_start: number
  page_end: number
  content: string | null
  status: Status
}

export interface ChunkUpdateRequest {
  heading: string
}

export interface ChatMessageResponse {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatResponse {
  answer: string
}

export interface ProfileResponse {
  id: string
  label: string | null
  background: string
  intent: string
}

export interface ProfileUpdateRequest {
  label: string | null
  background: string
  intent: string
}
