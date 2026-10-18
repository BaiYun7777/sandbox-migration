#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pkg_restore.py —— 交接包下载校验还原（sandbox-migration skill 脚本 · 2026-10-17 固化）
====================================================================================
用途：资料库 drive 节点的资产包（zip）批量还原。流程：取下载链 → 立即 curl 落盘
     （预签名短链会过期，取到即下）→ md5 校验 → 解压到工作目录 → 打印落位提示。

⚠️ 安全边界：
  - 全部产物只写 <workdir>（默认 /tmp/handover_pkgs），**绝不写 /workspace**；
  - 落位（cp 进 /workspace）不在本脚本内——由执行者按交接包操作说明人工确认后执行，
    符合「决策权归用户」红线；
  - md5 不符的包不解压，立即停下问用户。

用法：
    python3 pkg_restore.py --manifest manifest.json [--workdir /tmp/handover_pkgs]

manifest.json 格式（node_id/name/md5 必填）：
    [
      {"node_id": "77MsuRju0j3GUnUY90c4QH", "name": "包A_核心交接", "md5": "3ac050e7..."},
      ...
    ]

足彩推荐系统 2026-10-17 交接包现值见 references/资产地图_足彩推荐系统.md。
"""
import argparse, hashlib, json, os, subprocess, sys

def sh(cmd, **kw):
    return subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, **kw)

def get_download_url(node_id, library_dir='/root/.codebuddy/skills/library'):
    """调 library 技能 drive/get_download_link.py 取预签名下载链（短期有效）。"""
    r = sh(['python3', f'{library_dir}/drive/get_download_link.py', '--node-id', node_id])
    for line in (r.stdout or '').splitlines():
        if line.startswith('KS_DRIVE_DOWNLOAD '):
            return json.loads(line[len('KS_DRIVE_DOWNLOAD '):])['download_url']
    raise RuntimeError(f'取链失败 node={node_id}: {r.stdout[:200]} {r.stderr[:200]}')

def md5_of(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument('--manifest', required=True, help='manifest.json 路径')
    ap.add_argument('--workdir', default='/tmp/handover_pkgs')
    ap.add_argument('--library-dir', default='/root/.codebuddy/skills/library')
    ap.add_argument('--no-unzip', action='store_true', help='只下载校验，不解压')
    args, _ = ap.parse_known_args()

    manifest = json.load(open(args.manifest, encoding='utf-8'))
    pkg_dir = os.path.join(args.workdir, 'zips')
    os.makedirs(pkg_dir, exist_ok=True)

    ok = True
    for item in manifest:
        nid, name, exp = item['node_id'], item['name'], item['md5'].lower()
        zip_path = os.path.join(pkg_dir, f'{name}.zip')

        # 1) 取链即下
        try:
            url = get_download_url(nid, args.library_dir)
        except RuntimeError as e:
            ok = False
            print(f"[FAIL] {name}: {e}")
            continue
        r = sh(f'curl -sL --max-time 600 -o "{zip_path}" "{url}"')
        if r.returncode != 0 or not os.path.exists(zip_path):
            ok = False
            print(f"[FAIL] {name}: curl 失败 {r.stderr[:200]}")
            continue
        print(f"[下载] {name}: {os.path.getsize(zip_path)} 字节")

        # 2) md5 校验（不符不解压）
        got = md5_of(zip_path)
        if got != exp:
            ok = False
            print(f"[FAIL] {name}: md5 不符 got={got} exp={exp} —— 已保留原文件，请先问用户")
            continue
        print(f"[PASS] {name}: md5 一致 {got[:8]}…")

        # 3) 解压
        if not args.no_unzip:
            xdir = os.path.join(args.workdir, f'{name}_x')
            os.makedirs(xdir, exist_ok=True)
            r = sh(f'unzip -qo "{zip_path}" -d "{xdir}"')
            if r.returncode != 0:
                ok = False
                print(f"[FAIL] {name}: 解压失败 {r.stderr[:200]}")
                continue
            n_files = sum(len(fs) for _, _, fs in os.walk(xdir))
            print(f"[PASS] {name}: 已解压 → {xdir}（{n_files} 个文件）")

    print('=' * 60)
    print('PKG_RESTORE_ALL_PASS' if ok else 'PKG_RESTORE_HAS_FAILURES')
    if ok and not args.no_unzip:
        print('下一步（人工确认后执行，不在本脚本内）：')
        print('  1. 按交接包操作说明第三节逐目录 cp 落位到 /workspace；')
        print('  2. 注意：目标目录已存在时 `cp -r src dest/` 会嵌套成 dest/src，先核对再拷；')
        print('  3. 同名 README/文档冲突时先 diff，内容一致才覆盖，不一致停下问用户；')
        print('  4. 落位后跑文档规定的自检 4 项 + 在线复验（online_check.py）。')
    sys.exit(0 if ok else 1)

if __name__ == '__main__':
    main()
