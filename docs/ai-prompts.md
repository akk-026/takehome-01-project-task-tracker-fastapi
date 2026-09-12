# AI prompts

## Optional board

1. “Implement the optional drag-and-drop board view in the existing FastAPI/vanilla JavaScript task
   tracker. Reuse the server-provided legal lifecycle moves and status endpoint; do not duplicate
   lifecycle validation in the browser. Keep an accessible non-drag alternative.”

The first implementation tried to infer each task's legal targets from the detailed task list's
buttons. This worked visually but coupled board behavior to unrelated rendered controls. It was
replaced during review with board data passed directly from the project task response.
