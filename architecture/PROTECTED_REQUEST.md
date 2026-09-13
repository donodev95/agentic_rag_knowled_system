Streamlit
   │
   │ Authorization:
   │ Bearer <JWT>
   ▼
FastAPI
   │
   ▼
OAuth2PasswordBearer
   │ 
   ▼
get_current_user()
   │
   ├── decode token
   ├── verify signature
   ├── verify expiration
   ├── verify token type
   └── extract user UUID
   │
   ▼
get_user_by_id()
   │
   ▼
PostgreSQL
   │
   ▼
User active?
   │
   ▼
CurrentUserDep
   │
   ▼
Route