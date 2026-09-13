User question
    ↓
classify (requires retrieval or not)
    ↓
determine_retrieval
    ↓
   ┌─────────────────────┐
   │                     │
conversation         knowledge
   │                     │
generate            retrieve
                         ↓
                    grade_context
                         ↓
                enough evidence?
                   /           \
                 yes            no
                  ↓              ↓
              generate       rewrite query
                                  ↓
                               retrieve
                                  ↓
                               generate
                                  ↓
                         validate_sources
                                  ↓
                                 END

Historical messages are retrieved before creating a new Langgraph Orchestrator.
The new langgraph orchestrator is created for every new message.
How does the Agent remember the conversation?
    There are 2 main mechanisms:
    - PostgreSQL messages: The old messages are retrieved before run_agent() being executed.
    - Langgraph Checkpointer: 