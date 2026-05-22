import styles from "./button.module.css";

export default function Button({
  children,
  variant = "primary",
  loading = false,
  ...props
}) {
  return (
    <button
      className={`${styles.btn} ${styles[variant]}`}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading ? "Loading…" : children}
    </button>
  );
}
