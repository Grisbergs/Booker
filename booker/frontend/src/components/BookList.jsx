import { useEffect, useState } from "react";
import { getBooks, deleteBook } from "../api/books";

export default function BookList({ refreshTrigger, setEditingBook }) {
  const [books, setBooks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchBooks = async () => {
      try {
        setLoading(true);

        const data = await getBooks();

        console.log("BOOKS RESPONSE:", data);

        setBooks(data);
      } catch (err) {
        console.error("Fetch error:", err);
        setError("Failed to load books");
      } finally {
        setLoading(false);
      }
    };

    fetchBooks();
  }, [refreshTrigger]);

  const handleDelete = async (id) => {
    const confirmed = window.confirm("Delete this book?");

    if (!confirmed) return;

    try {
      await deleteBook(id);

      // remove from UI immediately
      setBooks((prevBooks) =>
        prevBooks.filter((book) => book.id !== id)
      );
    } catch (err) {
      console.error("Delete failed:", err);
      alert("Failed to delete book");
    }
  };

  if (loading) return <p>Loading books...</p>;
  if (error) return <p>{error}</p>;

  return (
    <div style={{ padding: "20px" }}>
      <h1>📚 Book Library</h1>

      {(books ?? []).length === 0 ? (
        <p>No books found.</p>
      ) : (
        <div style={{ display: "grid", gap: "10px" }}>
          {books.map((book) => (
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

              <button
                onClick={() => handleDelete(book.id)}
                style={{
                  marginTop: "10px",
                  padding: "6px 12px",
                  cursor: "pointer",
                }}
              >
                Delete
              </button>
              <button
                onClick={() => setEditingBook(book)}
               style={{  marginTop: "10px",
                 marginLeft: "8px",
                  padding: "6px 12px",
                  cursor: "pointer",}}
              >
              Edit
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}