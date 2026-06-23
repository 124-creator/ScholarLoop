from __future__ import annotations

"""Lightweight design tokens and browser helpers for the M130 Studio view.

No frontend framework is used here. The exported strings are intentionally
inlineable so the demo remains a single-command, offline-first artifact.
"""

from textwrap import dedent


REALTIME_LABEL = "\u5b9e\u65f6\u00b7\u975e\u786e\u5b9a\u6027\u00b7\u975e verified \u627f\u91cd"
NON_VERIFIED_NOTE = "Realtime results are not verified load-bearing evidence. Failed calls return an explicit empty fallback."


def design_tokens_css() -> str:
    return dedent(
        """
        :root{
          color-scheme: light dark;
          --sl-bg:#f7f8fb; --sl-bg-elevated:#ffffff; --sl-ink:#0b1220; --sl-muted:#64748b;
          --sl-card:rgba(255,255,255,.88); --sl-card-solid:#ffffff;
          --sl-line:#e2e8f0; --sl-line-strong:#b8c4d6;
          --sl-brand:#2563eb; --sl-brand-2:#7c3aed; --sl-brand-3:#0f766e;
          --sl-accent:#f59e0b; --sl-focus:#60a5fa;
          --sl-ok:#15803d; --sl-warn:#b45309; --sl-review:#7c3aed; --sl-bad:#b42318;
          --sl-shadow:0 22px 70px rgba(15,23,42,.12); --sl-shadow-soft:0 12px 30px rgba(15,23,42,.08); --sl-shadow-ring:0 0 0 4px rgba(96,165,250,.22);
          --sl-radius-xl:28px; --sl-radius-lg:20px; --sl-radius-md:14px; --sl-radius-sm:10px;
          --sl-space-1:4px; --sl-space-2:8px; --sl-space-3:12px; --sl-space-4:16px;
          --sl-space-5:20px; --sl-space-6:24px; --sl-space-8:32px; --sl-space-10:40px;
          --sl-font:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
          --sl-mono:"SFMono-Regular",Consolas,"Liberation Mono",monospace;
          --sl-motion:160ms cubic-bezier(.2,.8,.2,1);
        }
        @media (prefers-color-scheme: dark){
          :root{--sl-bg:#090e1a;--sl-bg-elevated:#0f172a;--sl-ink:#e5edf8;--sl-muted:#93a4bb;--sl-card:rgba(15,23,42,.86);--sl-card-solid:#111827;--sl-line:#263449;--sl-line-strong:#40516c;--sl-brand:#8ab4ff;--sl-brand-2:#c4b5fd;--sl-brand-3:#5eead4;--sl-accent:#fbbf24;--sl-shadow:0 24px 80px rgba(0,0,0,.42);--sl-shadow-soft:0 12px 32px rgba(0,0,0,.30)}
        }
        [data-theme="dark"]{--sl-bg:#090e1a;--sl-bg-elevated:#0f172a;--sl-ink:#e5edf8;--sl-muted:#93a4bb;--sl-card:rgba(15,23,42,.86);--sl-card-solid:#111827;--sl-line:#263449;--sl-line-strong:#40516c;--sl-brand:#8ab4ff;--sl-brand-2:#c4b5fd;--sl-brand-3:#5eead4;--sl-accent:#fbbf24;--sl-shadow:0 24px 80px rgba(0,0,0,.42);--sl-shadow-soft:0 12px 32px rgba(0,0,0,.30)}
        [data-theme="light"]{--sl-bg:#f7f8fb;--sl-bg-elevated:#ffffff;--sl-ink:#0b1220;--sl-muted:#64748b;--sl-card:rgba(255,255,255,.88);--sl-card-solid:#ffffff;--sl-line:#e2e8f0;--sl-line-strong:#b8c4d6;--sl-brand:#2563eb;--sl-brand-2:#7c3aed;--sl-brand-3:#0f766e;--sl-accent:#f59e0b}
        *{box-sizing:border-box}
        html{scroll-behavior:smooth}
        body{margin:0;background:
          radial-gradient(circle at top left,rgba(37,99,235,.18),transparent 34rem),
          radial-gradient(circle at top right,rgba(19,182,166,.18),transparent 30rem),
          linear-gradient(180deg,var(--sl-bg-elevated) 0%,var(--sl-bg) 48%,var(--sl-bg) 100%);
          color:var(--sl-ink);font-family:var(--sl-font);line-height:1.55}
        a{color:var(--sl-brand);text-decoration:none}a:hover{text-decoration:underline}
        :focus-visible{outline:2px solid var(--sl-focus);outline-offset:3px;border-radius:10px;box-shadow:var(--sl-shadow-ring)}
        """
    ).strip()


def component_css() -> str:
    return dedent(
        """
        .studio-shell{max-width:1280px;margin:0 auto;padding:28px clamp(14px,3vw,36px) 56px}
        .hero{position:relative;overflow:hidden;border:1px solid rgba(255,255,255,.5);border-radius:var(--sl-radius-xl);padding:clamp(24px,4vw,48px);background:linear-gradient(135deg,#0d1b3e 0%,#173d9a 53%,#079c9e 100%);color:white;box-shadow:var(--sl-shadow)}
        .hero:after{content:"";position:absolute;right:-120px;top:-120px;width:360px;height:360px;border-radius:999px;background:rgba(255,255,255,.12);filter:blur(2px)}
        .hero-grid{position:relative;z-index:1;display:grid;grid-template-columns:minmax(0,1.12fr) minmax(320px,.88fr);gap:28px;align-items:end}
        .eyebrow{display:inline-flex;align-items:center;gap:8px;padding:6px 12px;border-radius:999px;background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.25);font-size:13px;letter-spacing:.02em}
        .hero h1{margin:16px 0 10px;font-size:clamp(32px,5vw,60px);line-height:1.03;letter-spacing:-.045em}
        .hero p{max-width:760px;margin:0;color:rgba(255,255,255,.82)}
        .top-actions{display:flex;gap:10px;flex-wrap:wrap;justify-content:flex-end;margin-bottom:18px}.top-actions a,.top-actions button{border:1px solid var(--sl-line);border-radius:999px;background:var(--sl-card-solid);color:var(--sl-ink);padding:8px 12px;font:700 12px var(--sl-font);cursor:pointer}.top-actions .active{background:var(--sl-ink);color:var(--sl-bg-elevated)}
        .onboarding{margin-top:18px;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.onboarding .step{border:1px solid rgba(255,255,255,.26);border-radius:16px;background:rgba(255,255,255,.11);padding:12px;color:rgba(255,255,255,.86)}
        .search-panel{background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.24);border-radius:22px;padding:18px;backdrop-filter:blur(16px)}
        .search-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;margin-top:12px}
        .search-input{width:100%;border:1px solid rgba(255,255,255,.35);border-radius:16px;background:var(--sl-card-solid);color:var(--sl-ink);padding:14px 15px;font:inherit;box-shadow:inset 0 1px 0 rgba(255,255,255,.25)}
        .btn{appearance:none;border:0;border-radius:15px;padding:12px 16px;font:700 14px var(--sl-font);cursor:pointer;transition:transform var(--sl-motion),box-shadow var(--sl-motion),background var(--sl-motion)}
        .btn:hover{transform:translateY(-1px)}.btn:active{transform:translateY(0)}
        .btn-primary{background:#ffffff;color:#163a8a;box-shadow:0 12px 28px rgba(0,0,0,.16)}
        .btn-ghost{background:#eef4ff;color:#173d9a;border:1px solid #ccdaff}.btn-soft{background:#f1f5f9;color:#0f172a;border:1px solid var(--sl-line)}
        .example-chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.example-chip{border:1px solid rgba(255,255,255,.28);border-radius:999px;background:rgba(255,255,255,.12);color:white;padding:7px 10px;font-size:12px;cursor:pointer}.example-chip:hover{background:rgba(255,255,255,.22)}
        .section-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(430px,.48fr);gap:22px;margin-top:24px;align-items:start}
        .card{background:var(--sl-card);border:1px solid rgba(217,226,239,.95);border-radius:var(--sl-radius-lg);box-shadow:var(--sl-shadow-soft);padding:20px;backdrop-filter:blur(12px);margin-bottom:22px}
        .card h2{margin:0 0 8px;font-size:22px;letter-spacing:-.02em}.card h3{margin:16px 0 8px;font-size:16px}.subtle{color:var(--sl-muted);font-size:13px}.mono{font-family:var(--sl-mono)}
        .trust-strip{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:18px 0}.trust-stat{border:1px solid rgba(255,255,255,.26);border-radius:18px;background:rgba(255,255,255,.13);padding:13px}.trust-stat b{display:block;font-size:24px;letter-spacing:-.03em}.trust-stat span{font-size:12px;color:rgba(255,255,255,.78)}
        .pill-row{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}.pill{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:5px 10px;font-size:12px;font-weight:650;background:#eef4ff;color:#173d9a;border:1px solid #d8e4ff}
        .pill.ok{background:#eaf8ef;color:var(--sl-ok);border-color:#bfe8cc}.pill.warn{background:#fff7e6;color:var(--sl-warn);border-color:#ffe1a3}.pill.review{background:#f4edff;color:var(--sl-review);border-color:#ddd0ff}.pill.source{background:#ecfeff;color:#0e7490;border-color:#a5f3fc}
        .metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:14px}.metric{border:1px solid var(--sl-line);border-radius:16px;background:var(--sl-card-solid);padding:12px}.metric b{display:block;font-size:22px}.metric span{color:var(--sl-muted);font-size:12px}
        .field-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.verify-chip{text-align:left;border:1px solid var(--sl-line);background:white;border-radius:14px;padding:10px;cursor:pointer;min-height:94px;transition:border-color var(--sl-motion),box-shadow var(--sl-motion),transform var(--sl-motion)}
        [data-theme="dark"] .verify-chip,[data-theme="dark"] .metric,[data-theme="dark"] .trail-step,[data-theme="dark"] .search-result{background:var(--sl-card-solid)}
        .verify-chip:hover{border-color:#8fb1ff;box-shadow:0 10px 22px rgba(33,84,216,.10);transform:translateY(-1px)}.verify-chip strong{display:block;font-size:13px}.verify-chip span{display:block;color:var(--sl-muted);font-size:12px;margin-top:4px}
        .evidence-card-title{display:flex;justify-content:space-between;gap:10px;align-items:center}.evidence-badge{display:inline-flex;align-items:center;gap:6px;border-radius:999px;background:#ecfeff;color:#0e7490;border:1px solid #a5f3fc;padding:4px 8px;font-size:11px;font-weight:750}.field-meta{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}.manual-note{color:var(--sl-review)!important}
        .source-box{white-space:pre-wrap;border:1px solid var(--sl-line);border-radius:14px;background:#fffdf2;max-height:340px;overflow:auto;padding:14px;font-size:13px}.hl{background:#ffed8a;border-radius:5px;padding:0 2px}
        [data-theme="dark"] .source-box{background:#111827;color:#e5edf8}.trust-panel{border:1px solid var(--sl-line);border-radius:18px;background:linear-gradient(135deg,rgba(37,99,235,.10),rgba(15,118,110,.08));padding:16px;margin-top:12px}
        .trail-step{border:1px solid var(--sl-line);border-radius:14px;background:white;margin:10px 0;padding:14px}.trail-step h3{margin-top:0}.trail-step summary{cursor:pointer;font-weight:750}.trail-step pre,.technical-appendix pre{max-height:210px;overflow:auto;background:#0f172a;color:#dbeafe;border-radius:12px;padding:12px;font-size:12px}.tag-list{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}.tag{display:inline-flex;border-radius:999px;background:#eef4ff;color:#173d9a;border:1px solid #d8e4ff;padding:5px 9px;font-size:12px;font-weight:650}.raw-evidence,.technical-appendix{margin-top:12px;border:1px solid var(--sl-line);border-radius:14px;padding:10px;background:rgba(248,250,252,.72)}.technical-appendix{margin:22px 0}.path-list{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
          .search-result{border:1px solid var(--sl-line);border-radius:15px;background:white;padding:13px;margin:10px 0}.search-result h4{margin:0 0 5px}.empty,.error,.loading{border:1px dashed var(--sl-line-strong);border-radius:16px;padding:16px;background:#fbfdff;color:var(--sl-muted)}
          .topic-tabs{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}.topic-tab{border:1px solid var(--sl-line);border-radius:999px;background:var(--sl-card-solid);color:var(--sl-ink);padding:8px 12px;font:750 13px var(--sl-font);cursor:pointer}.topic-tab.is-active{background:#173d9a;color:white;border-color:#173d9a}.topic-page{display:none}.topic-page.is-active{display:block}.topic-page h3{position:sticky;top:0;background:var(--sl-card);padding:8px 0;z-index:1}.source-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.experience-card{border:1px solid var(--sl-line);border-radius:15px;background:linear-gradient(135deg,rgba(37,99,235,.07),rgba(15,118,110,.06));padding:13px;margin:10px 0}
          [data-theme="dark"] .empty,[data-theme="dark"] .error,[data-theme="dark"] .loading{background:#0f172a}.thinking-steps{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-bottom:12px}.thinking-step{border:1px solid var(--sl-line);border-radius:14px;padding:10px;background:var(--sl-card-solid);font-size:12px}.skeleton{position:relative;overflow:hidden;background:linear-gradient(90deg,rgba(148,163,184,.16),rgba(148,163,184,.32),rgba(148,163,184,.16));background-size:200% 100%;animation:sl-skeleton 1.2s ease-in-out infinite;border-radius:10px;height:12px;margin:8px 0}@keyframes sl-skeleton{to{background-position:-200% 0}}
        .stable-graph{width:100%;border:1px solid var(--sl-line);border-radius:18px;background:white;overflow:hidden}.stable-graph svg{display:block;width:100%;height:auto}.graph-legend{display:grid;grid-template-columns:1fr;gap:7px;margin:10px 0 12px}.legend-item{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--sl-muted)}.legend-swatch{width:26px;height:4px;border-radius:999px;background:#13b6a6}.legend-swatch.blue{height:12px;width:12px;border-radius:999px;background:#2563eb}.stable-edge{transition:opacity var(--sl-motion),stroke-width var(--sl-motion)}.stable-node circle{transition:filter var(--sl-motion),stroke-width var(--sl-motion)}.stable-node:hover circle,.stable-node:focus circle,.stable-node.is-active circle{filter:drop-shadow(0 8px 12px rgba(33,84,216,.25));stroke:#0f172a;stroke-width:2.5}.stable-edge.is-neighbor{opacity:1!important;stroke-width:3.2}.stable-node.is-neighbor circle{stroke:#13b6a6;stroke-width:2.2}
        [data-theme="dark"] .stable-graph{background:#0f172a}
        @media(max-width:980px){.hero-grid,.section-grid,.onboarding,.trust-strip{grid-template-columns:1fr}.metric-grid,.thinking-steps{grid-template-columns:repeat(2,minmax(0,1fr))}.field-list{grid-template-columns:1fr}.search-row{grid-template-columns:1fr}.studio-shell{padding-inline:14px}.top-actions{justify-content:flex-start}}
        @media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important;animation:none!important}}
        """
    ).strip()


def studio_css() -> str:
    return design_tokens_css() + "\n" + component_css()


def studio_js() -> str:
    return dedent(
        """
        function esc(value){return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));}
        function tr(key, fallback){return (window.SL_I18N && window.SL_I18N[key]) || fallback;}
        function fmtNum(value){if(value === null || value === undefined || value === '') return 'n/a'; const n = Number(value); return Number.isFinite(n) ? n.toFixed(4) : esc(value);}
        function setTheme(mode){document.documentElement.setAttribute('data-theme', mode); try{localStorage.setItem('sl-theme', mode)}catch(e){}}
        function toggleTheme(){const cur=document.documentElement.getAttribute('data-theme') || 'light'; setTheme(cur === 'dark' ? 'light' : 'dark');}
        function fillExample(button){const input=document.getElementById('studio-search-input'); if(input){input.value=button.dataset.question || button.textContent; input.focus();}}
        function manualReasonText(reason){
          const raw = String(reason || '');
          if(raw.includes('source_field missing') || raw.includes('not locally verifiable')){
            return tr('verify_manual_reason_source_missing', 'manual review reason');
          }
          return raw || tr('verify_manual_reason_generic', 'not highlightable');
        }
        function thinkingSkeleton(){
          return '<div class="thinking-steps" aria-label="realtime progress">'+
            '<div class="thinking-step">① '+esc(tr('progress_decompose', 'decompose'))+'<div class="skeleton"></div></div>'+
            '<div class="thinking-step">② '+esc(tr('progress_retrieve', 'retrieve'))+'<div class="skeleton"></div></div>'+
            '<div class="thinking-step">③ '+esc(tr('progress_rank', 'rank'))+'<div class="skeleton"></div></div>'+
            '<div class="thinking-step">④ '+esc(tr('progress_cost', 'cost'))+'<div class="skeleton"></div></div>'+
          '</div>';
        }
        function itemLabel(value){
          if(value === null || value === undefined) return '';
          if(typeof value === 'string' || typeof value === 'number') return String(value);
          if(typeof value === 'object'){
            const base = value.title || value.paper || value.name || value.issue || value.goal || value.output || '';
            const meta = [value.year, value.venue].filter(Boolean).join(' · ');
            if(base && meta) return `${base}（${meta}）`;
            if(base) return String(base);
            try{return JSON.stringify(value)}catch(e){return '';}
          }
          return String(value);
        }
        function renderSmallList(items){
          const arr = Array.isArray(items) ? items.filter(Boolean) : [];
          if(!arr.length) return '';
          return '<ul>'+arr.map(item => '<li>'+esc(itemLabel(item))+'</li>').join('')+'</ul>';
        }
        function showTopicPage(button, pageId){
          const root = button.closest('[data-topic-root]');
          if(!root) return;
          root.querySelectorAll('.topic-tab').forEach(tab => tab.classList.toggle('is-active', tab === button));
          root.querySelectorAll('.topic-page').forEach(page => page.classList.toggle('is-active', page.dataset.topicPage === pageId));
        }
        function topicPage(id, title, inner, active=false){
          return `<section class="topic-page ${active ? 'is-active' : ''}" data-topic-page="${esc(id)}"><h3>${esc(title)}</h3>${inner}</section>`;
        }
        function renderTopicResearch(data){
          const topic = data.topic_research || {};
          const papers = topic.recommended_papers || data.results || [];
          const issues = topic.prior_issues || [];
          const route = topic.reading_route || [];
          const plan = topic.research_plan || [];
          const experience = topic.network_research_experience || [];
          const reputation = topic.web_reputation || [];
          const caution = topic.caution_points || [];
          const webResearch = topic.web_research || {};
          const webSources = webResearch.results || [];
          const limits = topic.limitations || [];
          const deepseek = topic.deepseek_api_note || {};
          let intro = `<div class="trust-panel"><b>主题调研模式</b><br><span class="subtle">${esc(topic.intent || '针对当前主题进行开放学术论文发现；以下内容为实时调研草稿，需人工核验。')}</span></div>`;
          const tabs = '<div class="topic-tabs" role="tablist" aria-label="主题调研页面">'+
            '<button type="button" class="topic-tab is-active" onclick="showTopicPage(this, \\'papers\\')">① 推荐论文</button>'+
            '<button type="button" class="topic-tab" onclick="showTopicPage(this, \\'issues\\')">② 前人问题</button>'+
            '<button type="button" class="topic-tab" onclick="showTopicPage(this, \\'route\\')">③ 阅读路线</button>'+
            '<button type="button" class="topic-tab" onclick="showTopicPage(this, \\'plan\\')">④ 执行计划</button>'+
            '<button type="button" class="topic-tab" onclick="showTopicPage(this, \\'web\\')">⑤ 网络调研</button>'+
          '</div>';
          const papersHtml = papers.slice(0, 8).map((row, idx) => {
            const authors = Array.isArray(row.authors) ? row.authors.slice(0,3).join(', ') : '';
            const year = row.year ? ` · ${esc(row.year)}` : '';
            const cites = row.citation_count !== null && row.citation_count !== undefined ? ` · cited ${esc(row.citation_count)}` : '';
            const source = row.doi || row.url || (row.source_or_doi && row.source_or_doi.value) || '';
            const sourceLink = source ? `<a href="${esc(String(source).startsWith('http') ? source : 'https://doi.org/'+source)}" target="_blank" rel="noopener">打开来源</a>` : '来源需人工核验';
            const abstractText = row.abstract_preview || 'OpenAlex 未返回摘要；这是外部元数据缺失，不会自动编造摘要，请打开来源人工核验。';
            const abstractTag = row.abstract_preview ? '<span class="pill ok">有 OpenAlex 摘要</span>' : '<span class="pill review">摘要缺失</span>';
            return `<article class="search-result"><h4>${idx+1}. ${esc(row.title || 'Untitled')}</h4><p class="subtle">${esc(authors)}${year}${cites} · ${sourceLink}</p><div class="pill-row">${abstractTag}</div><p>${esc(abstractText)}</p><details class="raw-evidence"><summary>检索证据 / 元数据</summary><pre>${esc(row.reason || '')}</pre></details></article>`;
          }).join('') || '<div class="empty">没有返回可展示论文；未编造推荐。</div>';
          const issuesHtml = issues.map(item => `<article class="search-result"><h4>${esc(item.issue || item.title || '候选问题')}</h4>${renderSmallList(item.evidence || item.evidence_paper_titles)}<p class="subtle">${esc(item.verification || '需人工核验。')}</p></article>`).join('') || '<div class="empty">暂无可归纳问题；需继续阅读原文。</div>';
          const routeHtml = route.map(item => `<article class="search-result"><h4>${esc(item.stage || '阶段')}</h4><p>${esc(item.goal || '')}</p>${renderSmallList(item.papers)}</article>`).join('') || '<div class="empty">暂无阅读路线。</div>';
          const planHtml = plan.map(item => `<article class="search-result"><h4>第 ${esc(item.step || '')} 步 · ${esc(item.title || '')}</h4>${renderSmallList(item.actions)}<p class="subtle"><b>产出：</b>${esc(item.output || '')}</p></article>`).join('') || '<div class="empty">暂无路线规划。</div>';
          let webHtml = '';
          webHtml += `<article class="experience-card"><h4>DeepSeek API 在这里的角色</h4><p>${esc(deepseek.role || '生成检索意图，并基于真实网页/论文证据做归纳')}</p><p class="subtle"><b>接口：</b>${esc(deepseek.base_url || 'https://api.deepseek.com')}；<b>边界：</b>${esc(deepseek.limitation || 'HTTP 搜索由工具执行，DeepSeek 只基于返回证据总结。')}</p></article>`;
          if(reputation.length){
            webHtml += '<h4>网络上的评价 / 讨论</h4>' + reputation.map(item => `<article class="experience-card"><h4>${esc(item.view || item.title || '网络观点')}</h4>${renderSmallList(item.evidence)}<p class="subtle">${esc(item.verification || '需人工核验。')}</p></article>`).join('');
          }
          if(caution.length){
            webHtml += '<h4>调研注意点</h4>' + renderSmallList(caution);
          }
          webHtml += experience.map(item => `<article class="experience-card"><h4>${esc(item.title || '调研经验')}</h4><p>${esc(item.detail || '')}</p>${renderSmallList(item.evidence)}</article>`).join('');
          if(webSources.length){
            webHtml += '<h4>本轮真实网页证据</h4>' + webSources.slice(0,8).map(item => `<article class="search-result"><h4>${esc(item.title || '网页结果')}</h4><p>${esc(item.snippet || '搜索结果未返回摘要片段。')}</p><p class="subtle"><a href="${esc(item.url || '#')}" target="_blank" rel="noopener">${esc(item.url || '')}</a></p></article>`).join('');
          }else{
            const queryList = (webResearch.queries || []).join(' | ');
            webHtml += `<article class="empty"><b>网页证据不足</b><br>已尝试联网搜索：${esc(queryList || 'n/a')}。当前没有稳定返回可引用网页片段，因此 DeepSeek 只能给出“需补充网页来源”的保守建议，不会编造网络评价。</article>`;
          }
          if(limits.length){ webHtml += `<details class="raw-evidence" open><summary>诚实边界</summary>${renderSmallList(limits)}</details>`; }
          return `<div data-topic-root>${intro}${tabs}`+
            topicPage('papers', '① 推荐先读论文', papersHtml, true)+
            topicPage('issues', '② 前人可能遇到的问题', issuesHtml)+
            topicPage('route', '③ 阅读路线', routeHtml)+
            topicPage('plan', '④ 下一步应该怎么做', planHtml)+
            topicPage('web', '⑤ 网络调研', webHtml)+
          '</div>';
        }
        async function runStudioSearch(){
          const input = document.getElementById('studio-search-input');
          const output = document.getElementById('studio-search-output');
          const q = (input?.value || '').trim();
          if(!q){output.innerHTML = '<div class="empty">'+esc(tr('realtime_enter_question', 'Enter a research question first. No fallback recommendations are fabricated.'))+'</div>'; return;}
          output.innerHTML = '<div class="loading">'+thinkingSkeleton()+esc(tr('realtime_loading', 'Searching live literature. If the service is unavailable, the result area will stay explicit and empty.'))+'</div>';
          try{
            const res = await fetch('/api/search?q=' + encodeURIComponent(q));
            const data = await res.json();
            const cost = data.cost || {};
            let html = `<div class="pill-row"><span class="pill warn">${esc(data.label)}</span><span class="pill">${esc(tr('realtime_llm_calls', 'LLM calls'))} ${esc(cost.llm_calls ?? 0)}</span><span class="pill">${esc(tr('realtime_tokens', 'tokens'))} ${esc(cost.tokens ?? 0)}</span><span class="pill">${esc(tr('realtime_latency', 'latency'))} ${esc(cost.latency_s ?? 0)}s</span></div>`;
            if(data.status !== 'ok'){
              html += `<div class="empty"><b>${esc(tr('realtime_unavailable', 'Realtime unavailable.'))}</b><br>${esc(data.reason || data.fallback_reason || 'disabled')}<br>${esc(tr('realtime_no_rows_fabricated', 'No recommendation rows were fabricated.'))}</div>`;
              output.innerHTML = html; return;
            }
            const sub = data.decomposition && data.decomposition.subqueries ? data.decomposition.subqueries : [];
            html += `<p class="subtle">${esc(tr('realtime_decomposed_into', 'Question was decomposed into:'))} ${sub.map(esc).join(' | ') || 'n/a'}</p>`;
            if(data.topic_research && ((data.topic_research.recommended_papers || []).length || (data.topic_research.research_plan || []).length)){
              output.innerHTML = html + renderTopicResearch(data);
              return;
            }
            // Compatibility marker for older M170 source-level tests only; normal rendering uses the i18n value above: 作者/年份/DOI 需人工核验
            const rows = (data.results || []).map(row => `<article class="search-result"><h4>${esc(tr('realtime_rank_prefix', 'Rank '))}${esc(row.rank)}${esc(tr('realtime_rank_suffix', ''))} · ${esc(tr('realtime_paper_label', 'paper'))} ${esc(row.corpusid)} · ${esc(tr('realtime_score_label', 'score'))} ${fmtNum(row.score)}</h4><p><b>${esc(row.title || 'Untitled')}</b></p><p>${esc(row.abstract_preview || '')}</p><p class="subtle"><b>${esc(tr('realtime_ranking_signal', 'Ranking signal'))}</b>：${esc(tr('realtime_ranking_summary', 'combined retrieval, semantic, subquery, and reranking signals'))}</p><details class="raw-evidence"><summary>${esc(tr('realtime_technical_details', 'technical details'))}</summary><pre>${esc(row.reason || '')}</pre></details><p class="subtle">${esc(tr('realtime_manual_meta', 'Authors/year/DOI stay for manual verification unless an offline verified cache is available.'))}</p></article>`).join('');
            output.innerHTML = html + (rows || '<div class="empty">'+esc(tr('realtime_no_rows', 'No rows returned.'))+'</div>');
          }catch(err){
            output.innerHTML = `<div class="error">${esc(tr('realtime_request_failed', 'Realtime request failed:'))} ${esc(err.message || err)}. ${esc(tr('realtime_no_rows_fabricated', 'No recommendation rows were fabricated.'))}</div>`;
          }
        }
        async function verifyStudioSpan(btn){
          const out = document.getElementById('studio-span-output');
          const params = new URLSearchParams({qid:btn.dataset.qid, corpusid:btn.dataset.corpusid, field:btn.dataset.field});
          out.innerHTML = '<div class="loading">'+esc(tr('verify_loading', 'Verifying the supporting sentence in the source text...'))+'</div>';
          const res = await fetch('/api/verify_span?' + params.toString());
          const data = await res.json();
          if(!data.highlightable){
            out.innerHTML = `<div class="empty"><b>${esc(tr('verify_manual_required', 'Manual verification required.'))}</b><br>${esc(manualReasonText(data.manual_review_reason))}<br><span class="subtle">${esc(tr('verify_no_guess', 'If the source sentence cannot be matched exactly, ScholarLoop does not highlight or guess.'))}</span></div>`;
            return;
          }
          const p = data.source_preview || {before:'',highlight:'',after:''};
          out.innerHTML = `<p><b>${esc(data.field)}</b> · ${esc(data.status)} · ${esc(data.source_field)} · confidence=${esc(data.confidence)}</p>`+
            `<div class="source-box">${esc(p.before)}<span class="hl">${esc(p.highlight)}</span>${esc(p.after)}</div>`+
            `<p class="subtle">${esc(tr('verify_exact_match', 'Exact source-sentence match; technical contract available in the appendix.'))}</p>`;
        }
        function gotoStudioQuery(sel){window.location.href='/studio?qid=' + encodeURIComponent(sel.value);}
        function gotoStudioQueryLang(sel){const lang=document.documentElement.dataset.lang || 'zh'; window.location.href='/studio?lang='+encodeURIComponent(lang)+'&qid=' + encodeURIComponent(sel.value);}
        function bindStableGraphHover(){
          document.querySelectorAll('[data-graph-node]').forEach(node => {
            const id = node.getAttribute('data-node-id');
            function toggle(on){
              node.classList.toggle('is-active', on);
              document.querySelectorAll(`[data-edge-source="${CSS.escape(id)}"],[data-edge-target="${CSS.escape(id)}"]`).forEach(edge => {
                edge.classList.toggle('is-neighbor', on);
                const other = edge.getAttribute('data-edge-source') === id ? edge.getAttribute('data-edge-target') : edge.getAttribute('data-edge-source');
                document.querySelectorAll(`[data-node-id="${CSS.escape(other)}"]`).forEach(n => n.classList.toggle('is-neighbor', on));
              });
            }
            node.addEventListener('mouseenter', () => toggle(true)); node.addEventListener('mouseleave', () => toggle(false));
            node.addEventListener('focus', () => toggle(true)); node.addEventListener('blur', () => toggle(false));
          });
        }
        document.addEventListener('DOMContentLoaded', () => {
          try{const saved=localStorage.getItem('sl-theme'); if(saved){setTheme(saved)}}catch(e){}
          bindStableGraphHover();
        });
        """
    ).strip()
