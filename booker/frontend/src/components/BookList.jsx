import { useEffect, useState } from "react";
import { getBooks } from "../api/books";

export default function BookList({ refreshTrigger }) {
  const [books, setBooks] = useState([]);
  const [loading, setLoading] = useState(true);

useEffect(() => {
  const fetchBooks = async () => {
    const data = await getBooks();
    setBooks(data);
  };

  fetchBooks();
}, [refreshTrigger]);

  if (loading) return <p>Loading books...</p>;

  return (
    <div style={{ padding: "20px" }}>
      <h1>📚 Book Library</h1>

      {books.length === 0 ? (
        <p>No books found.</p>
      ) : (
        <div style={{ display: "grid", gap: "10px" }}>
          {(books ?? []).map((book) => (
            <div
              key={book.id}
              style={{
                border: "1px solid #ddd",
                padding: "10px",
                borderRadius: "8px",
              }}
            >
              <h3>{book.title}</h3>
              <p><strong>Author:</strong> {book.author}</p>
              <p>{book.description}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}