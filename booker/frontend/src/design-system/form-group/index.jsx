import styles from "./form-group.module.css";

export default function FormGroup({ label, htmlFor, error, hint, children }) {
  return (
    <div className={styles.group}>
      {label && (
        <label className={styles.label} htmlFor={htmlFor}>
          {label}
        </label>
      )}
      {children}
      {hint && !error && <p className={styles.hint}>{hint}</p>}
      {error && <p className={styles.error}>{error}</p>}
    </div>
  );
}
