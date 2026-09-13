Streamlit
   │
   │ POST /api/v1/auth/register
   │
   │ username
   │ email
   │ password
   ▼
FastAPI auth route
   │
   ▼
RegisterRequest
   │
   ├── validate username
   ├── validate email
   ├── validate password
   └── lowercase username/email
   │
   ▼
User Repository
   │
   ├── username exists?
   └── email exists?
   │
   ▼
hash_password()
   │
   ▼
Argon2
   │
   ▼
User(
    username,
    email,
    password_hash
)
   │
   ▼
PostgreSQL
   │
   ▼
COMMIT
   │
   ▼
UserPublic
   │
   ▼
Streamlit