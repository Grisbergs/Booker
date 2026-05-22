export default function Input({ label, ...props }) {
  return (
    <div style={{ marginBottom: "16px" }}>
      {label && <label>{label}</label>}

      <input
        {...props}
        style={{
          width: "100%",
          padding: "10px",
          borderRadius: "var(--radius-md)",
          border: "1px solid var(--border)",
          marginTop: "4px",
        }}
      />
    </div>
  );
}