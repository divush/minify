import { useEffect, useState } from 'react'
import { useProfile, useUpdateProfile } from '../hooks/useProfile'
import styles from './ProfileModal.module.css'

export default function ProfileModal({ onClose }: { onClose: () => void }) {
  const { data: profile } = useProfile()
  const updateProfile = useUpdateProfile()
  const [label, setLabel] = useState('')
  const [background, setBackground] = useState('')
  const [intent, setIntent] = useState('')

  useEffect(() => {
    if (profile) {
      setLabel(profile.label ?? '')
      setBackground(profile.background)
      setIntent(profile.intent)
    }
  }, [profile])

  const handleSave = () => {
    updateProfile.mutate({ label: label || null, background, intent }, { onSuccess: () => onClose() })
  }

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.card} onClick={(e) => e.stopPropagation()}>
        <div className={styles.head}>
          <div className={styles.title}>Reader profile</div>
          <button className={styles.iconBtn} onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>
        <div className={styles.hint}>
          Shapes how detailed or example-driven every chapter's writeup is. One profile for
          now — no switching between several yet.
        </div>

        <label className={styles.fieldLabel} htmlFor="profile-label">
          Label
        </label>
        <input id="profile-label" value={label} onChange={(e) => setLabel(e.target.value)} />

        <label className={styles.fieldLabel} htmlFor="profile-background">
          Background
        </label>
        <textarea
          id="profile-background"
          rows={2}
          value={background}
          onChange={(e) => setBackground(e.target.value)}
        />

        <label className={styles.fieldLabel} htmlFor="profile-intent">
          Intent
        </label>
        <textarea id="profile-intent" rows={2} value={intent} onChange={(e) => setIntent(e.target.value)} />

        <div className={styles.actions}>
          <button className={`${styles.btn} ${styles.btnGhost}`} onClick={onClose} type="button">
            Cancel
          </button>
          <button className={styles.btn} onClick={handleSave} disabled={updateProfile.isPending} type="button">
            {updateProfile.isPending ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
