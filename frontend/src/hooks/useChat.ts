import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { askChunk, getChunkChatHistory } from '../api/client'

export function useChatHistory(chunkId: string | undefined) {
  return useQuery({
    queryKey: ['chunk', chunkId, 'chat'],
    queryFn: () => getChunkChatHistory(chunkId!),
    enabled: !!chunkId,
  })
}

export function useAskChunk(chunkId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (question: string) => askChunk(chunkId, question),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chunk', chunkId, 'chat'] })
    },
  })
}
