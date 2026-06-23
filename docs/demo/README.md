# Demo surfaces

- Public static Studio: https://124-creator.github.io/ScholarLoop/
- Chinese static artifact: `docs/demo/m180-studio-zh.html`
- English static artifact: `docs/demo/m180-studio-en.html`
- Local runtime: `python -m scholarloop.demo.app --host 127.0.0.1 --port 8000`

GitHub Pages is intentionally static. The public homepage now intercepts `/api/search` with two public-safe five-page topic-research snapshots (`碳价格`, `large language model compression`) so recruiters can see:

1. recommended papers
2. prior issues
3. reading route
4. execution plan
5. web research notes

Realtime endpoints are source-level/local-runtime features. Local runtime can call OpenAlex + DeepSeek when credentials are configured; public unavailable states must stay explicit and never fabricate results.
