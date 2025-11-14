# Quick Start: LangChain Hyperfocus Agent

## TL;DR

```bash
# 1. Set environment variables
export LOCAL_OPENAI_BASE_URL='http://100.89.244.102:1234/v1'
export LOCAL_OPENAI_API_KEY='dummy-key'
export LOCAL_OPENAI_MODEL='qwen/qwen3-30b-a3b-2507'
export REMOTE_OPENAI_BASE_URL='http://your-remote:1234/v1'
export REMOTE_OPENAI_API_KEY='dummy-key'
export REMOTE_OPENAI_MODEL='your-model'

# 2. Run it!
poetry run hyperfocus-lc "List files in /tmp"
```

## What's Available

### Two Implementations

```bash
# Original (manual loop, custom routing)
poetry run hyperfocus "your message"

# LangChain (automatic, native tools)
poetry run hyperfocus-lc "your message"
```

### 13 Tools Ready

- **File**: read_file, create_file_with_content, append_to_file
- **Directory**: list_directory, get_current_directory, change_directory, create_directory
- **Shell**: execute_shell_command
- **Web**: readable_web_get
- **Image**: load_image (vision in Phase 4)
- **Task**: store_data_for_task, execute_simple_task, task_orientated_paging (Phase 4)

## Example Queries

```bash
# Simple conversation
poetry run hyperfocus-lc "Hello, who are you?"

# File operations
poetry run hyperfocus-lc "Read the file README.md"

# Multi-step task
poetry run hyperfocus-lc "Create /tmp/test.txt with 'Hello', then list /tmp to verify"

# Web scraping
poetry run hyperfocus-lc "Fetch https://example.com and summarize it"

# Shell command
poetry run hyperfocus-lc "What's my current directory? Use pwd command"
```

## Thread Persistence

```bash
# First message (creates thread)
poetry run hyperfocus-lc --thread-id work "Create /tmp/notes.txt with 'TODO: review code'"

# Second message (remembers context)
poetry run hyperfocus-lc --thread-id work "What did I just create?"
```

## Observability

If Phoenix is running:
```bash
# Start Phoenix (optional)
docker run -p 6006:6006 arizephoenix/phoenix:latest

# Set endpoint (or use default localhost:6006)
export PHOENIX_COLLECTOR_ENDPOINT='http://localhost:6006'

# Run agent - traces appear in Phoenix UI
poetry run hyperfocus-lc "your query"

# View at: http://localhost:6006
```

## Troubleshooting

### "Environment variables not set"
→ Set LOCAL_OPENAI_BASE_URL, LOCAL_OPENAI_API_KEY, LOCAL_OPENAI_MODEL (and REMOTE_* variants)

### "Connection refused"
→ Check your LLM server is running (LM Studio, vLLM, etc.)

### "No response"
→ Check console output for errors, verify model is loaded

### See more details
→ Check [PHASE3_TESTING.md](PHASE3_TESTING.md) for comprehensive testing guide

## What's Different from Original?

| Feature | Original | LangChain |
|---------|----------|-----------|
| Code | ~1,300 lines | ~700 lines (-48%) |
| Tool loop | Manual | Automatic |
| State | Custom dict | LangGraph |
| History | Manual append | Auto-checkpointed |
| Tools | JSON definitions | @tool decorator |

## Phase Status

✅ **Phase 1-3 Complete** - Basic functionality working
⏳ **Phase 4 Next** - Streaming, full context management, task system
📊 **Progress: 50% complete**

## Documentation

- [LANGCHAIN_MIGRATION_PLAN.md](LANGCHAIN_MIGRATION_PLAN.md) - Complete migration plan
- [PHASE1_COMPLETE.md](PHASE1_COMPLETE.md) - Dependencies & setup
- [PHASE2_COMPLETE.md](PHASE2_COMPLETE.md) - Tool migration
- [PHASE3_COMPLETE.md](PHASE3_COMPLETE.md) - Core agent implementation
- [PHASE3_TESTING.md](PHASE3_TESTING.md) - Detailed testing guide

## Next Steps

1. **Test** - Run the example queries above
2. **Compare** - Try same query with both `hyperfocus` and `hyperfocus-lc`
3. **Feedback** - Note any issues or differences
4. **Phase 4** - Full feature parity (streaming, tasks, multimodal)

---

**Ready to use!** 🚀 Start with a simple query and explore from there.
