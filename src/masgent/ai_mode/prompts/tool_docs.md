## read_doc_file Tool

MASgent includes a `read_doc_file` tool that lets you read documentation files from the `docs/` directory.
Use this tool whenever the user asks about:
- How the system works (architecture, task lifecycle, file lock, recovery)
- How to add new calculators or workflows
- User guides for executors, task runners, workflows
- Installation or quickstart instructions

The tool accepts a `doc_path` parameter which is a relative path within the `docs/` directory.
Common paths include:
- `developer_guide/architecture.md`
- `developer_guide/adding_calculator.md`
- `user_guide/executor.md`
- `user_guide/task_runner.md`
- `user_guide/workflow.md`
- `design/file_lock.md`
- `design/recovery.md`
- `design/task_lifecycle.md`
- `installation.md`
- `quickstart.md`

When the user asks a question that might be answered by documentation, use this tool before guessing.
