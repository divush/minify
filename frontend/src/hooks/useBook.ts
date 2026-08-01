import { useQuery } from '@tanstack/react-query'
import { getBookStatus, listBookChunks } from '../api/client'

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
