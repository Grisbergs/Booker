# Booker App Development Plan

## 1. Project Vision

Booker is an ebook library and reader application built with a Laravel API backend and React frontend, with a future Android app target.

The long-term goal is to support:
- EPUB reading
- PDF reading
- User-owned libraries
- Reading progress sync
- Notes and bookmarks
- Mobile-first reading experience
- Future Android support through React Native / Expo

---

## 2. Current Stack

### Backend
- Laravel
- Laravel Sail
- PostgreSQL
- Redis
- MinIO
- Mailpit

### Frontend
- React
- Vite
- Custom design system
- CSS modules
- Axios API layer

### Future Mobile
- React Native / Expo
- Shared API with Laravel backend
- Shared design tokens where possible

---

## 3. Current Progress

Completed:
- Laravel backend installed and running through Sail
- PostgreSQL database working
- React frontend created
- Book CRUD API started
- Book list UI working
- Create book form working
- Delete book functionality working
- Edit book functionality started
- Design system documentation created
- Initial reusable React design-system structure started

Current repo structure:

```text
booker/
├── backend/
└── frontend/
```

Recommended documentation structure:

```text
docs/
├── DESIGN_SYSTEM.md
├── BRAND_GUIDE.md
├── TOKENS.md
├── COMPONENTS.md
├── LAYOUT.md
├── ACCESSIBILITY.md
└── APP_PLAN.md
```

---

## 4. Development Phases

## Phase 1 — Stabilize Current CRUD App

Goal: Finish the basic book management web app.

### Features
- List books
- Create book
- Edit book
- Delete book
- Basic loading states
- Basic error handling
- Consistent design-system styling

### Tasks
- Finalize `BookForm`
- Finalize `BookList`
- Add edit/save flow
- Add delete confirmation
- Add empty state
- Add error state
- Replace inline styles with design-system components

### Success Criteria
- User can create, view, update, and delete book metadata from React
- Data persists in PostgreSQL
- UI uses reusable design-system components

---
phase 1 completed.
## Phase 2 — Design System Implementation

Goal: Turn the design system into reusable frontend building blocks.

### Components
- Button
- Input
- Textarea
- Card
- Alert
- Modal
- PageLayout
- FormGroup
- Badge

### Theme
- Light mode
- Dark mode
- CSS tokens
- Brand color variables
- Shared spacing/radius/shadow tokens

### Tasks
- Clean duplicate component folders
- Use folder-per-component structure
- Add CSS modules per component
- Add design-system exports
- Configure Vite aliases:
  - `@ds`
  - `@components`
  - `@api`

### Success Criteria
- App components use design-system imports
- No duplicate UI primitives
- New pages can be built with reusable components

---

## Phase 3 — Book File Upload

Goal: Allow users to upload real ebook files.

### Supported MVP Formats
- EPUB
- PDF

### Later Formats
- MOBI
- AZW
- AZW3
- DRM-free KFX where possible

### Backend Tasks
- Add file upload endpoint
- Validate file type and size
- Store files in MinIO
- Create `book_files` records
- Link uploaded file to a `book`
- Store:
  - original filename
  - file path
  - format
  - size
  - MIME type

### Frontend Tasks
- Add upload form
- Add file picker
- Show upload progress
- Show upload errors
- Show uploaded book in library

### Success Criteria
- User can upload an EPUB/PDF
- File is stored in MinIO
- Metadata is saved in PostgreSQL
- Book appears in library UI

---

## Phase 4 — Authentication

Goal: Support user accounts and private libraries.

### Backend
- Laravel Sanctum
- Register
- Login
- Logout
- Authenticated API routes
- User-owned books

### Database Changes
- Add `user_books`
- Associate books with users
- Protect access by user ID

### Frontend
- Login page
- Register page
- Auth state
- Protected library page
- Logout button

### Success Criteria
- Each user has their own library
- Unauthenticated users cannot access private book data

---

## Phase 5 — Reader Prototype

Goal: Open uploaded books in a reader view.

### EPUB
Use:
- EPUB.js

Reader features:
- Load EPUB file
- Render chapters
- Next/previous navigation
- Font size controls
- Light/dark reading mode

### PDF
Use:
- PDF.js / React PDF

PDF features:
- Page navigation
- Zoom
- Basic responsive display

### Success Criteria
- User can open an uploaded EPUB
- User can open an uploaded PDF
- Reader view works from the library page

---

## Phase 6 — Reading Progress

Goal: Track where users stop reading.

### Backend
Add `reading_progress` support:
- user_id
- book_id
- location
- progress_percent
- last_read_at

### Frontend
- Save progress periodically
- Restore last position
- Show progress in library card

### Success Criteria
- User can leave a book and resume from last position

---

## Phase 7 — Notes and Bookmarks

Goal: Add reader productivity features.

### Features
- Add bookmark
- Remove bookmark
- Add note
- View notes by book
- Jump to note location

### Tables
- `book_notes`
- `bookmarks` if separate from notes

### Success Criteria
- User can create and view notes/bookmarks per book

---

## Phase 8 — Android Strategy

Goal: Prepare Booker for Android.

### Recommended Approach
Use React Native / Expo.

Future structure:

```text
booker/
├── backend/
├── frontend/
└── mobile/
```

### Mobile App Responsibilities
- Login
- Library
- Download book files
- Offline reading
- EPUB/PDF reader
- Progress sync

### Backend Stays the Same
The Laravel API should serve:
- Web frontend
- Android app
- Future iOS app

### Success Criteria
- Android app can authenticate
- Android app can list user books
- Android app can open downloaded books

---

## 9. API Roadmap

### Books
```text
GET    /api/books
GET    /api/books/{id}
POST   /api/books
PUT    /api/books/{id}
DELETE /api/books/{id}
```

### Book Files
```text
POST   /api/books/{id}/files
GET    /api/books/{id}/files
DELETE /api/book-files/{id}
```

### Auth
```text
POST /api/register
POST /api/login
POST /api/logout
GET  /api/user
```

### Reading Progress
```text
GET  /api/books/{id}/progress
POST /api/books/{id}/progress
```

### Notes
```text
GET    /api/books/{id}/notes
POST   /api/books/{id}/notes
PUT    /api/notes/{id}
DELETE /api/notes/{id}
```

---

## 10. Database Roadmap

### Existing / Planned Tables
- users
- books
- book_files
- user_books
- reading_progress
- book_notes
- cache
- jobs

### Important Relationships
- User has many books through `user_books`
- Book has many book files
- User has one reading progress record per book
- User has many notes per book

---

## 11. Infrastructure Roadmap

### Local Development
- Laravel Sail
- PostgreSQL
- Redis
- MinIO
- Mailpit
- React Vite

### Future Production
Options:
- VPS with Docker Compose
- PostgreSQL managed or containerized
- MinIO or S3-compatible storage
- Queue worker for file processing
- Conversion worker for ebook normalization

---

## 12. Future File Conversion Strategy

Goal: Normalize compatible formats into EPUB.

### Convert to EPUB
- MOBI
- AZW
- AZW3
- DOCX
- TXT
- HTML

### Keep Native
- PDF

### Avoid
- DRM circumvention
- Native KFX rendering

### Tooling
- Calibre CLI
- Laravel queue jobs
- Redis queue worker

---

## 13. Recommended Next Steps

Immediate next steps:

1. Finish edit book functionality
2. Clean design-system component structure
3. Add upload endpoint for EPUB/PDF
4. Add upload UI in React
5. Store uploaded files in MinIO
6. Add reader prototype for EPUB
7. Add authentication

---

## 14. Version History

### v0.1
- Initial development plan created
- Laravel + React architecture selected
- Android path defined
- Ebook roadmap established
