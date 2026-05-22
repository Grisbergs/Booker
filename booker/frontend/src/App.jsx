import { useState } from "react";
import BookList from "./components/BookList";
import BookForm from "./components/BookForm";
import { useTheme } from "@ds/theme";
import styles from "./App.module.css";

function App() {
  const [refresh, setRefresh] = useState(0);
  const [editingBook, setEditingBook] = useState(null);
  const { theme, toggleTheme } = useTheme();

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1>Booker</h1>
        <button className={styles.themeToggle} onClick={toggleTheme}>
          {theme === "light" ? "Dark" : "Light"} mode
        </button>
      </div>

      <BookForm
        onBookCreated={() => setRefresh((r) => r + 1)}
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
