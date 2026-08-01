import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { listBooks, uploadBook } from '../api/client'

const BOOKS_KEY = ['books']

/** Polls while any book in the library is still queued/processing; stops once
 * everything has settled. */
export function useBooks() {
  return useQuery({
    queryKey: BOOKS_KEY,
    queryFn: listBooks,
    refetchInterval: (query) => {
      const books = query.state.data
      const stillWorking = books?.some((b) => b.status === 'processing' || b.status === 'queued')
      return stillWorking ? 3000 : false
    },
  })
}

export function useUploadBook() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ file, title }: { file: File; title?: string }) => uploadBook(file, title),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: BOOKS_KEY })
    },
  })
}
