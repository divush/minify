import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useUploadBook } from '../hooks/useBooks'
import styles from './UploadRow.module.css'

export default function UploadRow() {
  const [isDragging, setIsDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()
  const upload = useUploadBook()

  const submit = (file: File) => {
    setError(null)
    upload.mutate(
      { file },
      {
        onSuccess: (result) => navigate(`/books/${result.book_id}`),
        onError: (err: Error) => setError(err.message),
      },
    )
  }

  return (
    <div>
      <label
        className={`${styles.row} ${isDragging ? styles.dragging : ''}`}
        onDragOver={(e) => {
          e.preventDefault()
          setIsDragging(true)
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setIsDragging(false)
          const file = e.dataTransfer.files[0]
          if (file) submit(file)
        }}
      >
        <span className={styles.icon} aria-hidden="true">
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12 3v12" />
            <path d="M7 8l5-5 5 5" />
            <path d="M5 21h14a2 2 0 0 0 2-2v-5H3v5a2 2 0 0 0 2 2z" />
          </svg>
        </span>
        <span>{upload.isPending ? 'Uploading…' : 'Upload a new book (PDF)'}</span>
        <input
          type="file"
          accept="application/pdf"
          className={styles.hiddenInput}
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) submit(file)
            e.target.value = ''
          }}
        />
      </label>
      {error && <div className={styles.error}>{error}</div>}
    </div>
  )
}
