import { useEffect, useRef, useState } from 'react'
import { useAskChunk, useChatHistory } from '../hooks/useChat'
import { useChunkContent } from '../hooks/useChunkContent'
import styles from './MarginaliaPanel.module.css'
import ReactMarkdown from 'react-markdown'

interface Props {
  chunkId: string
  onClose: () => void
}

export default function MarginaliaPanel({ chunkId, onClose }: Props) {
  const { data: history } = useChatHistory(chunkId)
  const { data: chunk } = useChunkContent(chunkId)
  const ask = useAskChunk(chunkId)
  const [question, setQuestion] = useState('')
  const threadRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight })
  }, [history, ask.isPending])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = question.trim()
    if (!trimmed) return
    setQuestion('')
    ask.mutate(trimmed)
  }

  const isEmpty = history && history.length === 0 && !ask.isPending

  return (
    <aside className={styles.panel}>
      <div className={styles.head}>
        <div className={styles.label}>
          <span>Marginalia — {chunk?.heading ?? 'this chapter'}</span>
          <button onClick={onClose} aria-label="Close" type="button">
            ✕
          </button>
        </div>
        <div className={styles.caption}>
          Answers are grounded in this chapter only — switch chapters to ask about a different one.
        </div>
      </div>
      <div className={styles.thread} ref={threadRef}>
        {isEmpty && <div className={styles.empty}>No questions yet — ask something about this chapter.</div>}
        {history?.map((message, i) => (
          <div key={i} className={`${styles.bubble} ${styles[message.role]}`}>
            <div className={styles.who}>{message.role === 'user' ? 'You' : 'Minify'}</div>
            <div className={styles.body}><ReactMarkdown>{message.content}</ReactMarkdown></div>
          </div>
        ))}
        {ask.isPending && ask.variables && (
          <div className={`${styles.bubble} ${styles.user}`}>
            <div className={styles.who}>You</div>
            <div className={styles.body}>{ask.variables}</div>
          </div>
        )}
        {ask.isPending && (
          <div className={`${styles.bubble} ${styles.assistant} ${styles.typing}`}>
            <div className={styles.who}>Minify</div>
            <div className={styles.body}>thinking…</div>
          </div>
        )}
      </div>
      <form className={styles.form} onSubmit={handleSubmit}>
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about this chapter…"
          autoComplete="off"
        />
        <button type="submit" disabled={ask.isPending || !question.trim()}>
          Ask
        </button>
      </form>
    </aside>
  )
}
