#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
online_check.py —— 任务端在线状态自检（sandbox-migration skill 脚本 · 2026-10-17 固化 · 2026-10-18 基线更新）
====================================================================================
用途：新沙箱/新对话开局第一步。GET 任务端 prompt 现值，与配置基线逐项比对。
     md5 不符 = 有人动过线上或版本已推进，先问用户，严禁带病 PUT。

⚠️ 本脚本**只读**：仅 GET，无任何 PUT / 写操作 / 凭证调用。

自检项（缺配置项自动跳过并提示）：
  ① 各任务在线 prompt 字符数 + md5 == 配置基线
  ② 两端 λ 内嵌块（fence 提取）逐字节同源（配了 CANON 才查）
  ③ λ 内嵌块 + 行尾 == skill canonical（字符数 + md5 前缀）
  ④ 版本特征串在档（FEATURES 列表，如 r11 numpy 修复 / r7 双自由度）
  ⑤ skill canonical 落盘复验
  ⑥ 本地归档件 md5 复验（ARCHIVE 列表，文件缺失记 WARN 不记 FAIL）

配置改这里（换版本时只改 CONFIG 块）：
"""
import hashlib, os, sys

# ==================== CONFIG（随版本更新） ====================
API_BASE = 'http://auth.proxy/codebuddy/v2/as/scheduler/tasks'

# tid: (期望字符数, 期望 md5)
# 2026-10-18 15:4x 更新：453 r3→r4（候选窗口改革+P0/P1/P2 修复）；660 r21→r22（13:55 批入账+行数归正 406+瘦身）
TASKS = {
    '4539406': (235891, '6c9af0ce18872ef521c2d17690b2b853'),   # v4.0.0-r4
    '6600221': (256311, '820aa981eee6401e130548b1a114ff0f'),   # v4.0.0-r22
}

# skill canonical（λ 求解器唯一 canonical）；不需要则置 None
CANON = {
    'path': '/root/.codebuddy/skills/football-prediction/scripts/lambda-source.py',
    'chars': 49546,
    'md5_prefix': '19c322cedbb8',
    'block_sig': 'def market_lambda',      # λ 块内唯一函数签名
}

# 版本特征串：(显示名, 必须同时命中的子串元组)
FEATURES = [
    ('r11 numpy 修复', ('try:', 'import numpy as np', 'arange')),
    ('r7 双自由度', ('TAU_LO', 'SSE_MAX', '坐标下降')),
]

# 本地归档件复验：((目录, 文件名, 期望 md5), …)；文件不存在记 WARN
# 2026-10-18 二次更新：10-17 r2 存档（4 件）+ 10-18 r3/r21 存档（4 件）+ 10-18 r4/r22 存档（4 件，含链式 before/after）
ARCHIVE = [
    ('/workspace/赔率研究_每日数据集/规范/线上prompt存档/20261017_v4.0.0-r2_λ内嵌块对齐skill实体_453r2_660r2',
     '453_v4.0.0-r2_candidate.md', '961b4645f6bc373e5961203a13783d9f'),
    ('/workspace/赔率研究_每日数据集/规范/线上prompt存档/20261017_v4.0.0-r2_λ内嵌块对齐skill实体_453r2_660r2',
     '660_v4.0.0-r2_candidate.md', '6a7332658c0e566d9a58afc40fd2d81f'),
    ('/workspace/赔率研究_每日数据集/规范/线上prompt存档/20261017_v4.0.0-r2_λ内嵌块对齐skill实体_453r2_660r2',
     '453_before.md', '3b511b6b605a561d24b7b483250ea3e0'),
    ('/workspace/赔率研究_每日数据集/规范/线上prompt存档/20261017_v4.0.0-r2_λ内嵌块对齐skill实体_453r2_660r2',
     '660_before.md', 'b7803e1a15bfd736c10fb23e1a4a6b99'),
    ('/root/.codebuddy/skills/football-prediction/规范/线上prompt存档/20261018_脚本取用唯一来源纪律_453r3_660r21',
     '453_before.txt', '961b4645f6bc373e5961203a13783d9f'),
    ('/root/.codebuddy/skills/football-prediction/规范/线上prompt存档/20261018_脚本取用唯一来源纪律_453r3_660r21',
     '453_after.txt', '9ddb85e22e9a0c12774fc87c106bb68a'),
    ('/root/.codebuddy/skills/football-prediction/规范/线上prompt存档/20261018_脚本取用唯一来源纪律_453r3_660r21',
     '660_before.txt', '50746351a6b8d5ef66de3d9ff5d8a9f7'),
    ('/root/.codebuddy/skills/football-prediction/规范/线上prompt存档/20261018_脚本取用唯一来源纪律_453r3_660r21',
     '660_after.txt', 'd27657b881f9df60c8aa9d38ce157623'),
    ('/root/.codebuddy/skills/football-prediction/规范/线上prompt存档/20261018_候选窗口改革与P0P1P2修复_453r4',
     '453_before.txt', '9ddb85e22e9a0c12774fc87c106bb68a'),
    ('/root/.codebuddy/skills/football-prediction/规范/线上prompt存档/20261018_候选窗口改革与P0P1P2修复_453r4',
     '453_after.txt', '6c9af0ce18872ef521c2d17690b2b853'),
    ('/workspace/赔率研究_每日数据集/规范/线上prompt存档/20261018_660_r22_瘦身',
     '660_before.txt', 'd27657b881f9df60c8aa9d38ce157623'),
    ('/workspace/赔率研究_每日数据集/规范/线上prompt存档/20261018_660_r22_瘦身',
     '660_after.txt', '820aa981eee6401e130548b1a114ff0f'),
]
# ================================================================

def get_prompt(tid):
    import requests
    r = requests.get(f'{API_BASE}/{tid}', timeout=60)
    return r.json()['data']['agentConfig']['prompt']

def extract_blocks(prompt, sig='def market_lambda'):
    """全量扫描 fence 块，返回所有含 sig 的块（不含行尾）。

    注意：不能用「标题行 hint 定位」——prompt 里多处含 lambda-source.py 字样
    （沿革条、脚本表、grep 命令），会框错区间返回空块（2026-10-17 实测踩坑）。
    且 453 prompt 有 3 个块都含 market_lambda 字样（定位脚本/λ 本体/调度块），
    单靠签名不唯一，需配合 canonical md5 筛选（见 find_canonical_block）。
    """
    lines = prompt.split('\n')
    blocks = []
    i, n = 0, len(lines)
    while i < n:
        if lines[i].strip().startswith('```'):
            for j in range(i + 1, n):
                if lines[j].strip() == '```':
                    body = '\n'.join(lines[i + 1:j])
                    if sig in body:
                        blocks.append(body)
                    i = j + 1
                    break
            else:
                break
        else:
            i += 1
    return blocks

def find_canonical_block(prompt, canon):
    """在含签名的候选块中，按 canonical md5（含行尾口径）筛选，断言恰好 1 个。"""
    import hashlib
    cands = extract_blocks(prompt, canon['block_sig'])
    hits = [b for b in cands
            if hashlib.md5((b + '\n').encode()).hexdigest().startswith(canon['md5_prefix'])]
    if len(hits) != 1:
        raise ValueError(f'候选块 {len(cands)} 个，其中匹配 canonical md5 的 {len(hits)} 个（应恰为 1）')
    return hits[0]

def main():
    ok = True
    prompts = {}

    # ① 各任务 md5 / 字符数
    for tid, (exp_len, exp_md5) in TASKS.items():
        p = get_prompt(tid)
        prompts[tid] = p
        md5 = hashlib.md5(p.encode()).hexdigest()
        good = (md5 == exp_md5 and len(p) == exp_len)
        ok &= good
        print(f"[{'PASS' if good else 'FAIL'}] {tid} len={len(p)} md5={md5[:8]}… (期望 {exp_len}/{exp_md5[:8]}…)")

    tids = list(TASKS)
    if CANON and len(tids) >= 2:
        # ② 两端 λ 块同源
        blocks = {}
        for tid in tids:
            try:
                blocks[tid] = find_canonical_block(prompts[tid], CANON)
            except ValueError as e:
                ok = False
                print(f"[FAIL] {tid} λ 块提取失败: {e}")
        if len(blocks) == len(tids):
            ref = blocks[tids[0]]
            same = all(b == ref for b in blocks.values())
            ok &= same
            print(f"[{'PASS' if same else 'FAIL'}] 两端 λ 内嵌块同源（{len(ref)} 字符）")

            # ③ λ 块 + 行尾 == canonical
            canon_text = ref + '\n'
            md5c = hashlib.md5(canon_text.encode()).hexdigest()
            good = (len(canon_text) == CANON['chars'] and md5c.startswith(CANON['md5_prefix']))
            ok &= good
            print(f"[{'PASS' if good else 'FAIL'}] λ 块 == canonical {len(canon_text)} 字符 / {md5c[:8]}…")

            # ④ 版本特征串
            for name, feats in FEATURES:
                hit = all(f in ref for f in feats)
                ok &= hit
                print(f"[{'PASS' if hit else 'FAIL'}] {name} 特征在档")

        # ⑤ canonical 落盘复验
        if os.path.exists(CANON['path']):
            disk = open(CANON['path'], encoding='utf-8').read()
            good = hashlib.md5(disk.encode()).hexdigest().startswith(CANON['md5_prefix'])
            ok &= good
            print(f"[{'PASS' if good else 'FAIL'}] canonical 落盘复验 {os.path.basename(CANON['path'])}")
        else:
            print(f"[WARN] canonical 文件不在档: {CANON['path']}")

    # ⑥ 本地归档件复验（缺失记 WARN）
    for adir, fname, exp in ARCHIVE:
        path = os.path.join(adir, fname)
        if not os.path.exists(path):
            print(f"[WARN] 归档件不在档（跳过）: {fname}")
            continue
        d = open(path, 'rb').read()
        good = hashlib.md5(d).hexdigest() == exp
        ok &= good
        print(f"[{'PASS' if good else 'FAIL'}] 归档 {fname} md5 复验")

    print('ONLINE_CHECK_ALL_PASS' if ok else 'ONLINE_CHECK_HAS_FAILURES')
    sys.exit(0 if ok else 1)

if __name__ == '__main__':
    main()
