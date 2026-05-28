import styles from "./page-layout.module.css";

export default function PageLayout({ children, title }) {
  return (
    <div className={styles.page}>
      <div className={styles.container}>
        {title && <h1 className={styles.title}>{title}</h1>}
        {children}
      </div>
    </div>
  );
}
