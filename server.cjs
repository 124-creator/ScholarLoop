const http = require("http");
const fs = require("fs");
const path = require("path");
const { URL } = require("url");

loadDotEnv(path.join(__dirname, ".env"));

const apiSearchHandler = require("./api/search.js");

const HOST = process.env.HOST || "127.0.0.1";
const PORT = Number(process.env.PORT || 3000);
const ROOT = __dirname;

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".ico": "image/x-icon",
};

function loadDotEnv(file) {
  if (!fs.existsSync(file)) return;
  const text = fs.readFileSync(file, "utf8");
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq < 0) continue;
    const key = line.slice(0, eq).trim();
    let value = line.slice(eq + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    if (key && process.env[key] === undefined) process.env[key] = value;
  }
}

function send(res, status, body, headers = {}) {
  res.writeHead(status, headers);
  res.end(body);
}

function sendJson(res, status, payload) {
  send(res, status, JSON.stringify(payload), {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
  });
}

function serveFile(res, filePath, cacheControl = "public, max-age=60") {
  fs.readFile(filePath, (error, body) => {
    if (error) {
      send(res, 404, "Not found", { "content-type": "text/plain; charset=utf-8" });
      return;
    }
    const ext = path.extname(filePath).toLowerCase();
    send(res, 200, body, {
      "content-type": MIME[ext] || "application/octet-stream",
      "cache-control": cacheControl,
    });
  });
}

function adaptResponse(res) {
  return {
    statusCode: 200,
    headersSent: false,
    setHeader(name, value) {
      res.setHeader(name, value);
    },
    status(code) {
      this.statusCode = code;
      res.statusCode = code;
      return this;
    },
    json(payload) {
      if (!res.headersSent) {
        res.statusCode = this.statusCode || res.statusCode || 200;
        res.setHeader("content-type", "application/json; charset=utf-8");
      }
      res.end(JSON.stringify(payload));
      this.headersSent = true;
      return this;
    },
    end(body = "") {
      if (!res.headersSent) res.statusCode = this.statusCode || res.statusCode || 200;
      res.end(body);
      this.headersSent = true;
      return this;
    },
  };
}

async function handleApiSearch(req, res, parsedUrl) {
  const query = {};
  for (const [key, value] of parsedUrl.searchParams.entries()) query[key] = value;
  const adaptedReq = {
    method: req.method,
    url: req.url,
    headers: req.headers,
    query,
  };
  const adaptedRes = adaptResponse(res);
  await apiSearchHandler(adaptedReq, adaptedRes);
}

const server = http.createServer(async (req, res) => {
  const parsedUrl = new URL(req.url || "/", `http://${req.headers.host || "localhost"}`);
  const pathname = decodeURIComponent(parsedUrl.pathname);

  try {
    if (pathname === "/healthz") {
      return sendJson(res, 200, { status: "ok", service: "scholarloop", time: new Date().toISOString() });
    }

    if (pathname === "/api/search") {
      return await handleApiSearch(req, res, parsedUrl);
    }

    if (pathname === "/favicon.ico") {
      return send(res, 204, "");
    }

    if (pathname === "/" || pathname === "/index.html") {
      return serveFile(res, path.join(ROOT, "index.html"), "no-cache");
    }

    if (pathname === "/studio-en.html") {
      return serveFile(res, path.join(ROOT, "studio-en.html"), "no-cache");
    }

    const safePath = path.normalize(pathname).replace(/^(\.\.[/\\])+/, "");
    const candidate = path.join(ROOT, safePath);
    if (candidate.startsWith(ROOT) && fs.existsSync(candidate) && fs.statSync(candidate).isFile()) {
      return serveFile(res, candidate);
    }

    return send(res, 404, "Not found", { "content-type": "text/plain; charset=utf-8" });
  } catch (error) {
    return sendJson(res, 500, {
      status: "error",
      reason: error && error.message ? error.message : String(error),
    });
  }
});

server.listen(PORT, HOST, () => {
  console.log(`ScholarLoop server listening at http://${HOST}:${PORT}`);
});
