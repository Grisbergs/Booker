import { useState } from "react";
import BookList from "./components/BookList";
import BookForm from "./components/BookForm";

function App() {
  const [refresh, setRefresh] = useState(0);

  const handleBookCreated = () => {
    setRefresh((r) => r + 1);
  };

  return (
    <div style={{ padding: "20px" }}>
      <BookForm onBookCreated={handleBookCreated} />
      <BookList refreshTrigger={refresh} />
    </div>
  );
}

export default App;
 
