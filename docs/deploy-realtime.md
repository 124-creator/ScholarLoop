# Realtime deployment guide

GitHub Pages is static: it can serve HTML/CSS/JS, but it cannot run Python/Node backend code or keep API keys secret. ScholarLoop therefore uses two realtime layers:

1. **Public GitHub Pages fallback**: browser-side OpenAlex realtime search. It requires no key and lets visitors search arbitrary topics.
2. **Serverless DeepSeek mode**: deploy this repository to Vercel or another serverless host. The `/api/search` function calls OpenAlex and optionally DeepSeek from the server side, so the key is not exposed in browser JavaScript.

## Option A: public page with browser OpenAlex realtime

Already enabled on:

```text
https://124-creator.github.io/ScholarLoop/
```

Visitors can input a topic and the page will call OpenAlex directly from the browser. If OpenAlex or the browser blocks the request, the page falls back to public-safe static snapshots rather than fabricating rows.

## Option B: Vercel DeepSeek realtime backend

1. Import `https://github.com/124-creator/ScholarLoop` into Vercel.
2. Keep the default project root.
3. Add environment variables in Vercel Project Settings:

```text
DEEPSEEK_API_KEY=your_server_side_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
ALLOWED_ORIGIN=https://124-creator.github.io
```

4. Deploy.
5. Test:

```text
https://YOUR-VERCEL-PROJECT.vercel.app/api/health
https://YOUR-VERCEL-PROJECT.vercel.app/api/search?q=carbon%20price%20forecasting
```

6. To make GitHub Pages call the Vercel backend, open the GitHub Pages page once and run in browser DevTools Console:

```js
localStorage.setItem('SCHOLARLOOP_API_BASE', 'https://YOUR-VERCEL-PROJECT.vercel.app')
```

For a permanent public configuration, set `window.SCHOLARLOOP_API_BASE` in `index.html` after the backend URL is known, then rebuild/push the static page.

## Safety rule

Never place `DEEPSEEK_API_KEY` or any LLM key in `index.html`, `studio-en.html`, frontend JavaScript, GitHub Actions logs, or public JSON. Keys belong only in server-side environment variables.
