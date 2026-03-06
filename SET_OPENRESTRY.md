# KSRPC OpenResty 最小修改说明

给新人的唯一要求：

- 只在站点代理 `location` 里新增一行 `proxy_next_upstream off;`

示例（`/www/sites/<domain>/proxy/root.conf`）：

```nginx
location ^~ / {
    proxy_pass http://<upstream_name_or_ip_port>;
    proxy_next_upstream off;
}
```

说明：

- 不需要改其它参数。
- 修改后执行 `openresty -t` 检查配置，再 `openresty -s reload` 生效。
