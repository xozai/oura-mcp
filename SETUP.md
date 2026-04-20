# Oura MCP Server — Setup Guide

Connect your Oura Ring data to Claude in 4 steps.

---

## 1. Get Your Oura Personal Access Token

1. Go to **https://cloud.ouraring.com/personal-access-tokens**
2. Click **"Create New Personal Access Token"**
3. Give it a name (e.g. `claude-mcp`) and copy the token — you won't see it again

---

## 2. Install Dependencies

```bash
cd /Users/jleos/Documents/GitHub/oura-mcp
pip install -r requirements.txt
```

---

## 3. Register with Claude Code

Add this to `~/.claude/claude_desktop_config.json` (or your Claude Code MCP config):

```json
{
  "mcpServers": {
    "oura": {
      "command": "python",
      "args": ["/Users/jleos/Documents/GitHub/oura-mcp/oura_mcp.py"],
      "env": {
        "OURA_ACCESS_TOKEN": "your_token_here"
      }
    }
  }
}
```

---

## Available Tools

| Tool | What it does |
|------|-------------|
| `oura_get_personal_info` | Profile: age, weight, height, sex |
| `oura_get_daily_sleep` | Daily sleep scores + sub-scores |
| `oura_get_sleep_sessions` | Detailed per-session data (REM, deep, HRV…) |
| `oura_get_daily_readiness` | Readiness scores + contributing factors |
| `oura_get_daily_activity` | Steps, calories, activity scores |
| `oura_get_heart_rate` | Time-series BPM data |
| `oura_get_daily_spo2` | Nightly blood oxygen (Gen 3+ only) |
| `oura_get_daily_stress` | Stress & recovery balance |
| `oura_get_workouts` | Workout sessions (type, duration, HR…) |
| `oura_get_sessions` | Mindfulness & meditation sessions |

---

## Example Prompts

- "How did I sleep last week?"
- "What's been dragging down my readiness score?"
- "How many steps did I take yesterday?"
- "Show my heart rate during sleep on April 15"
- "Did I meditate this week?"
- "What workouts did I do in the last 10 days?"

---

## Troubleshooting

- **Unauthorized error**: Double-check your token is correct and `OURA_ACCESS_TOKEN` is set.
- **No data returned**: Make sure your ring has synced in the Oura app recently.
- **SpO2 / Stress empty**: Requires Oura Ring Generation 3 or later.
