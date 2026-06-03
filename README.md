# Browsli

Interactive terminal browser for search and web browsing.

## Run

```powershell
cd E:\Workspace\python\browsli
$env:TAVILY_API_KEY = "your-tavily-key"
$env:OPENAI_API_KEY = "your-openai-api-key"
uv run browsli
```

## Configuration

Browsli reads non-secret settings from the user config file reported by:

```powershell
uv run python -c "from browsli.config import default_config_path; print(default_config_path())"
```

Default OpenAI LLM configuration:

```toml
[llm]
name = "openai"
model = "gpt-4o-mini"
api_key_env = "OPENAI_API_KEY"
timeout_seconds = 45
```

Ollama Cloud configuration:

```toml
[llm]
name = "ollama-cloud"
model = "gpt-oss:120b"
api_key_env = "OLLAMA_API_KEY"
timeout_seconds = 45
```

Codex and ChatGPT subscriptions are not API credentials. Use the `openai` provider with an `OPENAI_API_KEY` for OpenAI API access.

