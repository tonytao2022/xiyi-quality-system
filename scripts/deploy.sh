#!/bin/bash
# 兮易AI智体·一键部署脚本
set -e
echo "===== 兮易AI智体 部署脚本 ====="

# 依赖
pip3 install -r ../requirements.txt

# 后端
cp ../backend/xiyi_server.py /opt/xiyi-server/
systemctl stop xiyi-server 2>/dev/null || true
cp ../config/xiyi-server.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable xiyi-server
systemctl start xiyi-server

# 前端
cp -r ../frontend/*.html /var/www/html/steel-platform/

# Nginx
cp ../config/nginx-default.conf /etc/nginx/sites-enabled/default

# 数据库
mysql -u root -p < ../scripts/init_db.sql

echo "✅ 部署完成!"
echo "前端: http://localhost/xiyi-index.html"
echo "后端: http://localhost:8890/health"
