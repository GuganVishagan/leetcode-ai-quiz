# ⚡ LeetCode AI Quiz Coach

A local AI-powered quiz tool that connects to your LeetCode account, fetches your actual submitted code, and quizzes you on it — one question at a time, like a real interviewer.

Built for engineers who are grinding LeetCode daily but want to go beyond just solving problems — to truly being able to explain and defend their solutions under pressure.

---

## What it does

- Connects to LeetCode via GraphQL API using your session cookies
- Fetches your accepted submissions — today / last 3 days / last 7 days / last 30 days
- Pulls the **exact code you submitted**, with runtime and memory stats
- Uses **Claude (Anthropic AI)** to quiz you on your own code, one question at a time

---

## 8 Quiz Modes

| Mode | What it does |
|------|-------------|
| ⏱ **TC / SC** | Walks you through time and space complexity of your actual code |
| 🔍 **Code Block** | Picks a specific snippet from your code and asks why you wrote it that way |
| 💡 **Core Concept** | Identifies the pattern (Kadane's, sliding window, etc.) and tests your understanding |
| 🐛 **Bug Hunt** | Introduces a subtle bug into your code — you have to find it |
| 🙈 **Blind Recall** | Explain your entire approach from scratch, no peeking at the code |
| 🧩 **Pattern Match** | Gives you a new problem and asks which pattern applies |
| 🎤 **Mock Interview** | Full FAANG-style back and forth simulation |
| ⚖️ **Compare Approaches** | Your solution vs an alternative — justify the trade-offs |

---

## Voice Support

- 🎤 Click the mic button and speak your answer — it fills the text box automatically
- 🔊 Toggle voice on to have Claude read its questions aloud
- Uses the browser's built-in Web Speech API — completely free, no extra API calls

---

## Setup (5 steps)

**Requirements:** Python 3 (no pip installs needed), Google Chrome, Anthropic API key

### 1. Clone the repo
```bash
git clone https://github.com/GuganVishagan/leetcode-ai-quiz.git
cd leetcode-ai-quiz
```

### 2. Run the server
```bash
python3 leetcode_server.py
```

### 3. Open the app
```
http://localhost:8765
```

### 4. Get your LeetCode cookies
- Open [leetcode.com](https://leetcode.com) while logged in
- Press `F12` → Application → Cookies → `leetcode.com`
- Copy the values for `LEETCODE_SESSION` and `csrftoken`

### 5. Get your Anthropic API key
- Go to [console.anthropic.com](https://console.anthropic.com)
- API Keys → Create Key
- Paste it into the app

That's it. Pick a problem you solved, pick a quiz mode, and get grilled.

---

## Tech Stack

- **Python stdlib** — `HTTPServer`, `urllib` — zero pip installs, runs anywhere
- **LeetCode GraphQL API** — fetches real submissions and code (ref: [akarsh1995/leetcode-graphql-queries](https://github.com/akarsh1995/leetcode-graphql-queries))
- **Claude API (Anthropic)** — powers all quiz generation
- **Web Speech API** — free voice I/O, built into Chrome
- **Vanilla HTML/CSS/JS** — no React, no framework

---

## Security

- Everything runs **locally on your machine**
- Your LeetCode cookies and API key are entered in the browser at runtime
- Nothing is stored, logged, or sent anywhere except directly to LeetCode and Anthropic

---

## Why I built this

Solving 500 LeetCode problems and still freezing when someone asks *"why did you reset currSum to 0 here?"* is a real thing.

Explaining your solution is a completely different skill from writing it. This tool makes you practice both, every single day.

---

## License

MIT
