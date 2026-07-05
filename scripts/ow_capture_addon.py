# -*- coding: utf-8 -*-
"""mitmproxy addon: 自动从 datamsapi 请求里提取 token + roleId，写入 creds.json
免责: 仅供学习交流，遵守网易DD服务条款，自负风险。抓完请用 setup_capture.ps1 -Cleanup 还原。
"""
import json, os, re
from mitmproxy import http

CREDS_FILE = os.path.join(os.path.dirname(__file__), "creds.json")
_seen = set()

def response(flow: http.HTTPFlow):
    try:
        url = flow.request.pretty_url
        if "datamsapi.ds.163.com/v1/a19ld5tool/" not in url:
            return
        # 从 query 提取 token 和 roleId
        qs = flow.request.query
        token = qs.get("token")
        roleid = qs.get("roleId")
        if not token or not roleid:
            return
        key = (token, roleid)
        if key in _seen:
            return
        _seen.add(key)
        creds = {}
        if os.path.exists(CREDS_FILE):
            creds = json.load(open(CREDS_FILE, encoding="utf-8"))
        creds["token"] = token
        creds["roleId"] = roleid
        creds["server"] = qs.get("server", "1")
        creds["dts"] = qs.get("dts", "2026")
        json.dump(creds, open(CREDS_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"\n*** CREDS CAPTURED *** token={token[:12]}... roleId={roleid} -> {CREDS_FILE}\n")
    except Exception as e:
        print(f"capture addon err: {e}")
