import { useQuery } from '@tanstack/react-query'
import { getChunkContent } from '../api/client'

export function useChunkContent(chunkId: string | undefined) {
  return useQuery({
    queryKey: ['chunk', chunkId, 'content'],
    queryFn: () => getChunkContent(chunkId!),
    enabled: !!chunkId,
  })
}
