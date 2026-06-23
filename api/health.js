module.exports = function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.status(200).json({ ok: true, service: "ScholarLoop realtime API", has_deepseek_key: Boolean(process.env.DEEPSEEK_API_KEY || process.env.LLM_API_KEY) });
};
