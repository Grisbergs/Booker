import { useState } from "react";
import BookList from "./components/BookList";
import BookForm from "./components/BookForm";

function App() {
  const [refresh, setRefresh] = useState(0);
  const [editingBook, setEditingBook] = useState(null);

  const handleBookCreated = () => {
    setRefresh((r) => r + 1);
  };

  return (
    <div style={{ padding: "20px" }}>
     <BookForm
  onBookCreated={handleBookCreated}
  editingBook={editingBook}
  setEditingBook={setEditingBook}
/>

<BookList
  refreshTrigger={refresh}
  setEditingBook={setEditingBook}
/>
    </div>
  );
}

export default App;
 
