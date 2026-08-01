import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getProfile, updateProfile } from '../api/client'
import type { ProfileUpdateRequest } from '../api/types'

const PROFILE_KEY = ['profile']

export function useProfile() {
  return useQuery({ queryKey: PROFILE_KEY, queryFn: getProfile })
}

export function useUpdateProfile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (update: ProfileUpdateRequest) => updateProfile(update),
    onSuccess: (data) => {
      queryClient.setQueryData(PROFILE_KEY, data)
    },
  })
}
