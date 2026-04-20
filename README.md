# Oura Ring MCP Server

Connect your Oura Ring health data to Claude via the [Model Context Protocol](https://modelcontextprotocol.io).

## Requirements

- Python 3.10+
- An [Oura Ring](https://ouraring.com) with a synced account
- Claude Code or Claude Desktop

## Installation

**1. Clone the repo**

```bash
git clone https://github.com/joseleos/oura-mcp.git
cd oura-mcp
```

**2. Install dependencies**

```bash
pip install -r requirements.txt
```

**3. Get your Oura Personal Access Token**

Go to [https://cloud.ouraring.com/personal-access-tokens](https://cloud.ouraring.com/personal-access-tokens), create a new token, and copy it.

**4. Add to your Claude MCP config**

Edit `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "oura": {
      "command": "python",
      "args": ["/path/to/oura-mcp/oura_mcp.py"],
      "env": {
        "OURA_ACCESS_TOKEN": "your_token_here"
      }
    }
  }
}
```

Restart Claude Code for the server to load.

## Available Tools

| Tool | Description |
|------|-------------|
| `oura_get_personal_info` | Profile: age, weight, height, sex |
| `oura_get_daily_sleep` | Daily sleep scores + sub-scores |
| `oura_get_sleep_sessions` | Per-session data: REM, deep, HRV, efficiency |
| `oura_get_daily_readiness` | Readiness scores + contributing factors |
| `oura_get_daily_activity` | Steps, calories, activity scores |
| `oura_get_heart_rate` | Time-series BPM data |
| `oura_get_daily_spo2` | Nightly blood oxygen — Gen 3+ only |
| `oura_get_daily_stress` | Stress & recovery balance — Gen 3+ only |
| `oura_get_workouts` | Workout sessions: type, duration, HR |
| `oura_get_sessions` | Mindfulness & meditation sessions |

All collection tools accept optional `start_date` / `end_date` (YYYY-MM-DD) and default to the last 7 days. Pass `response_format: "json"` to get raw API data.

## Example Prompts

- "How did I sleep last week?"
- "What's been dragging down my readiness score?"
- "How many steps did I average this month?"
- "Show my heart rate during sleep on April 15"
- "Did I meditate this week?"
- "What workouts did I do in the last 10 days?"

## Troubleshooting

| Error | Fix |
|-------|-----|
| Unauthorized | Verify `OURA_ACCESS_TOKEN` is set correctly and hasn't expired |
| No data returned | Make sure your ring has synced in the Oura app recently |
| SpO2 / Stress empty | Requires Oura Ring Generation 3 or later |
| Rate limit exceeded | Wait a moment and retry |
