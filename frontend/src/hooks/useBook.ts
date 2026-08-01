import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { confirmBook, getBookStatus, listBookChunks, updateChunkHeading } from '../api/client'

/** Polls while the book itself is still queued/processing. */
export function useBookStatus(bookId: string) {
  return useQuery({
    queryKey: ['book', bookId, 'status'],
    queryFn: () => getBookStatus(bookId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'processing' || status === 'queued' ? 2000 : false
    },
  })
}

/** Polls while any individual chunk hasn't reached a terminal status yet. */
export function useBookChunks(bookId: string) {
  return useQuery({
    queryKey: ['book', bookId, 'chunks'],
    queryFn: () => listBookChunks(bookId),
    refetchInterval: (query) => {
      const chunks = query.state.data
      const stillWorking = chunks?.some((c) => c.status !== 'ready' && c.status !== 'failed')
      return stillWorking ? 2000 : false
    },
  })
}

/** Confirms the reviewed chapters and starts summarization. */
export function useConfirmBook(bookId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => confirmBook(bookId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['book', bookId, 'status'] })
    },
  })
}

/** Renames one chunk's chapter title — only allowed while the book is
 * awaiting confirmation (enforced server-side too). */
export function useRenameChunk(bookId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ chunkId, heading }: { chunkId: string; heading: string }) =>
      updateChunkHeading(chunkId, heading),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['book', bookId, 'chunks'] })
    },
  })
}
