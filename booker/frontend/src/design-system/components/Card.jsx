export default function Card({ children }) {
  return (
    <div
      style={{
        background: "var(--surface)",
        padding: "20px",
        borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-sm)",
        border: "1px solid var(--border)",
      }}
    >
      {children}
    </div>
  );
}