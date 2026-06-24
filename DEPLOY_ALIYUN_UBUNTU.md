# ScholarLoop 阿里云 Ubuntu 部署手册

目标：把当前 **前端静态页 + Node.js 后端 `/api/search` + OpenAlex + DeepSeek** 部署到阿里云轻量应用服务器。

## 1. 阿里云控制台先做这几步

1. 等实例状态从“准备中”变成“运行中”。
2. 点实例卡片，复制公网 IP。
3. 点“设置密码”，设置 root 密码。
4. 左侧“防火墙”放行：
   - `22`：SSH
   - `80`：HTTP
   - `443`：HTTPS，后续绑定域名和证书时用
   - `3000`：只建议临时测试，Nginx 配好后可关闭

> 大陆服务器绑定域名正式访问需要 ICP 备案。未备案前可以先用 `http://公网IP` 测试。

## 2. 登录服务器

Windows PowerShell：

```powershell
ssh root@你的公网IP
```

首次登录输入 `yes`，再输入你设置的 root 密码。

## 3. 安装基础环境

```bash
apt update
apt install -y git curl nginx

curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt install -y nodejs

npm i -g pm2
node -v
npm -v
pm2 -v
```

## 4. 拉取代码

```bash
mkdir -p /var/www
cd /var/www
git clone https://github.com/124-creator/ScholarLoop.git scholarloop
cd scholarloop
```

如果仓库还没有包含 `server.cjs` 等部署文件，先把本地最新版本 push 到 GitHub 后再 clone/pull。

## 5. 配置 DeepSeek Key

```bash
cp .env.example .env
nano .env
```

填写：

```bash
DEEPSEEK_API_KEY=你的真实key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
HOST=127.0.0.1
PORT=3000
ALLOWED_ORIGIN=*
```

保存：`Ctrl+O` 回车，退出：`Ctrl+X`。

## 6. 启动 Node 后端

```bash
cd /var/www/scholarloop
pm2 start ecosystem.config.cjs
pm2 save
pm2 startup
```

检查：

```bash
pm2 status
curl http://127.0.0.1:3000/healthz
curl "http://127.0.0.1:3000/api/search?q=机器学习"
```

看到 JSON 返回即正常。

## 7. 配置 Nginx

```bash
cp /var/www/scholarloop/deploy/nginx-scholarloop.conf /etc/nginx/sites-available/scholarloop
ln -sf /etc/nginx/sites-available/scholarloop /etc/nginx/sites-enabled/scholarloop
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx
```

浏览器打开：

```text
http://你的公网IP
```

API 测试：

```text
http://你的公网IP/api/search?q=机器学习
```

## 8. 后续绑定域名和 HTTPS

大陆服务器域名需要备案。备案完成后：

1. 域名 DNS 添加 A 记录，指向服务器公网 IP。
2. 修改 `/etc/nginx/sites-available/scholarloop`：

```nginx
server_name 你的域名;
```

3. 申请 HTTPS 证书。可用阿里云免费证书或 Certbot。

Certbot 示例：

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d 你的域名
```

## 9. 更新代码

```bash
cd /var/www/scholarloop
git pull
pm2 restart scholarloop
```

## 10. 常见问题

### 页面能打开，但实时搜索失败

检查：

```bash
pm2 logs scholarloop --lines 80
curl "http://127.0.0.1:3000/api/search?q=碳价格"
```

确认 `.env` 里有 `DEEPSEEK_API_KEY`。

### 外网打不开

检查阿里云轻量服务器防火墙是否放行 `80`。

### 3000 端口打不开

正常。正式访问走 Nginx 的 80/443，不需要把 3000 永久暴露给公网。

### 要不要上传 Claude 的 30KB 静态包？

不作为主方案。它是静态展示版，不能调用 DeepSeek 后端。当前部署方案保留实时后端能力，更适合简历和 HR 展示。
