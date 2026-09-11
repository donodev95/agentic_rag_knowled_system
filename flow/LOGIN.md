Streamlit
   │
   │ email + password
   ▼
POST /api/v1/auth/login
   │
   ▼
LoginRequest
   │
   ▼
get_user_by_email()
   │
   ▼
PostgreSQL
   │
   ▼
User
   │
   ├── exists?
   ├── active?
   └── verify_password?
             │
             ▼
      create_access_token()
             │
             ▼
            JWT
             │
             ▼
       TokenResponse
             │
             ▼
        Streamlit
             │
             ▼
st.session_state.token