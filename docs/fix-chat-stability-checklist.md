# Chat stability regression checks

- Search for a term that excludes the active session, then send a message.
- Start the app with Ollama stopped and confirm the error banner appears while saved sessions remain visible.
- Edit an earlier user message and confirm deleted messages disappear before generation begins.
- Retry an assistant message and confirm the old response disappears before generation begins.
- Interrupt or fail an Ollama stream after partial output and confirm the partial assistant response is not restored after refresh.
- Confirm message labels and action buttons contain no emoji.
