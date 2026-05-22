export default function Button({
  children,
  variant = "primary",
  loading = false,
  ...props
}) {
  const styles = {
    primary: {
      background: "var(--primary-500)",
      color: "white",
      border: "none",
    },
    secondary: {
      background: "transparent",
      color: "var(--primary-700)",
      border: "1px solid var(--border)",
    },
    danger: {
      background: "#d32f2f",
      color: "white",
      border: "none",
    },
  };

  return (
    <button
      style={{
        padding: "10px 16px",
        borderRadius: "var(--radius-md)",
        cursor: "pointer",
        ...styles[variant],
      }}
      disabled={loading}
      {...props}
    >
      {loading ? "Loading..." : children}
    </button>
  );
}