# KSRPC OpenResty 配置手册（脱敏版，仅 OpenResty）

本文使用占位符，避免直接暴露真实域名、主机名与内网信息。

## 1. 占位符约定

- `${EDGE_NODE}`: OpenResty 所在边缘节点（例如你的 tx 节点）
- `${SITE_DOMAIN}`: 对外访问域名
- `${SITE_CONF}`: 站点主配置路径（通常在 `conf.d` 下）
- `${PROXY_CONF}`: 站点代理配置路径（通常在 `sites/<domain>/proxy/root.conf`）
- `${TAILSCALE_IP}`: Tailscale 内网 IP
- `${KSRPC_PORT}`: ksrpc 监听端口（当前约定 `19991`）

上游写法统一为：

```nginx
proxy_pass http://${TAILSCALE_IP}:${KSRPC_PORT};
```

说明：`${TAILSCALE_IP}:${KSRPC_PORT}` 是 Tailscale 内网地址与 ksrpc 端口组合，不应作为公网地址公开。

---

## 2. 改动范围（仅两处）

1. `${SITE_CONF}`
2. `${PROXY_CONF}`

---

## 3. 默认配置（修改前关键片段）

```nginx
# ${PROXY_CONF}
location ^~ / {
    proxy_pass http://${TAILSCALE_IP}:${KSRPC_PORT};
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $http_connection;
    proxy_http_version 1.1;
}
```

---

## 4. 最小改动配置（修改后）

```nginx
# ${SITE_CONF}
map $http_upgrade $ws_connection_upgrade { # MODIFIED: 新增 WS Connection 映射
    default upgrade; # MODIFIED
    '' close;        # MODIFIED
}

server {
    listen 443 ssl;
    server_name ${SITE_DOMAIN};
    include /www/sites/${SITE_DOMAIN}/proxy/*.conf;
}
```

```nginx
# ${PROXY_CONF}
location ^~ / {
    proxy_pass http://${TAILSCALE_IP}:${KSRPC_PORT};

    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $ws_connection_upgrade; # MODIFIED: 原 $http_connection
    proxy_set_header Authorization $http_authorization; # MODIFIED: 透传 BasicAuth

    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Port $server_port;

    proxy_http_version 1.1;
    proxy_connect_timeout 60s; # MODIFIED
    proxy_send_timeout 600s;   # MODIFIED
    proxy_read_timeout 600s;   # MODIFIED
}
```