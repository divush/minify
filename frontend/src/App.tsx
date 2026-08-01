import { Route, Routes } from 'react-router-dom'
import LibraryView from './views/LibraryView'
import BookView from './views/BookView'

function App() {
  return (
    <Routes>
      <Route path="/" element={<LibraryView />} />
      <Route path="/books/:bookId" element={<BookView />} />
    </Routes>
  )
}

export default App
