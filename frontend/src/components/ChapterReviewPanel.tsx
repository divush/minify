import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useBookChunks, useConfirmBook, useRenameChunk } from '../hooks/useBook'
import type { ChunkSummary } from '../api/types'
import styles from './ChapterReviewPanel.module.css'

interface RowProps {
  chunk: ChunkSummary
  onRename: (chunkId: string, heading: string) => void
}

function ChapterRow({ chunk, onRename }: RowProps) {
  const fallback = `Section ${chunk.index + 1}`
  const [value, setValue] = useState(chunk.heading ?? fallback)

  const commit = () => {
    const trimmed = value.trim()
    const current = chunk.heading ?? fallback
    if (trimmed && trimmed !== current) {
      onRename(chunk.id, trimmed)
    } else if (!trimmed) {
      setValue(current)
    }
  }

  return (
    <li className={styles.row}>
      <input
        className={styles.titleInput}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
        }}
        aria-label={`Chapter ${chunk.index + 1} title`}
      />
      <span className={styles.pages}>
        pp. {chunk.page_start}–{chunk.page_end}
      </span>
    </li>
  )
}

export default function ChapterReviewPanel({ bookId }: { bookId: string }) {
  const { data: chunks } = useBookChunks(bookId)
  const confirmBook = useConfirmBook(bookId)
  const renameChunk = useRenameChunk(bookId)

  return (
    <div className={styles.wrap}>
      <div className={styles.card}>
        <Link to="/" className={styles.backLink}>
          ← Library
        </Link>
        <h1>Review the chapters</h1>
        <p className={styles.hint}>
          Rename anything that looks off, then confirm to start generating tailored writeups —
          this is the step before any LLM calls are made.
        </p>

        {chunks && chunks.length > 0 ? (
          <ul className={styles.list}>
            {chunks.map((chunk) => (
              <ChapterRow
                key={chunk.id}
                chunk={chunk}
                onRename={(chunkId, heading) => renameChunk.mutate({ chunkId, heading })}
              />
            ))}
          </ul>
        ) : (
          <p className={styles.status}>Extracting chapters…</p>
        )}

        <button
          className={styles.confirmBtn}
          type="button"
          disabled={!chunks || chunks.length === 0 || confirmBook.isPending}
          onClick={() => confirmBook.mutate()}
        >
          {confirmBook.isPending ? 'Starting…' : 'Confirm and start summarizing →'}
        </button>
      </div>
    </div>
  )
}
