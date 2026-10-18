#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fence_extract.py —— 从任务 prompt 文件中提取内嵌代码块（sandbox-migration skill 脚本 · 2026-10-17 固化）
====================================================================================================
用途：恢复 skill 实体内嵌脚本（lambda-source.py / upset-factor.py / guard 脚本 / jc-calc.py /
     方糖推送等）时的通用提取器。按签名子串定位 fence 块，落盘 + md5 断言。

⚠️ 已处理的坑（2026-10-17 迁移实测）：
  - 收尾 ``` 与最后一行内容同写一行（行内闭合）：按「行首 ``` 或行尾 ```」双规则识别闭合；
  - ```python 围栏头既是上一块闭栏又是下一块开栏的场景：按行号区间精确切割，不用计数器；
  - 多块命中 + 给了 --expect-md5：自动选中 md5 匹配的块，无需手工 --index；
  - md5 口径：同时比对「块体原样」与「块体+行尾换行」两种（canonical 惯例为含行尾），
    任一前缀匹配即 PASS；提取结果不符时 exit 1，先核对再落盘，严禁带病覆盖。

用法：
    python3 fence_extract.py --file 453_prompt.md --sig "def market_lambda" --out lambda.py \
        [--expect-md5 19c322ce...] [--expect-chars 49545] [--index 0] [--py-compile]

    # 列出全部候选块（不落盘）：
    python3 fence_extract.py --file 453_prompt.md --sig "market_lambda" --list
"""
import argparse, hashlib, os, py_compile, sys

def find_blocks(text, sig):
    """返回 [(块文本, 起始行号)]：开栏行(行首 ```) 到闭栏行(行首 ``` 或行尾 ```) 之间。"""
    lines = text.split('\n')
    blocks = []
    i, n = 0, len(lines)
    while i < n:
        if lines[i].strip().startswith('```'):
            j2, body = None, None
            for j2 in range(i + 1, n):
                stripped = lines[j2].strip()
                if stripped == '```':
                    body = lines[i + 1:j2]
                    close_style = 'line'
                    break
                if lines[j2].rstrip().endswith('```') and not stripped.startswith('```'):
                    last = lines[j2].rstrip()[:-3].rstrip('\r')
                    body = lines[i + 1:j2] + [last]
                    close_style = 'inline'
                    break
            if body is not None:
                block_text = '\n'.join(body)
                if sig in block_text:
                    blocks.append((block_text, i + 1, close_style))
                i = j2 + 1
                continue
        i += 1
    return blocks

def md5_of(s):
    return hashlib.md5(s.encode()).hexdigest()

def md5_match(block, exp):
    exp = exp.lower()
    return md5_of(block).startswith(exp) or md5_of(block + '\n').startswith(exp)

def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument('--file', required=True, help='prompt 文件路径')
    ap.add_argument('--sig', required=True, help='签名子串（在块体内命中）')
    ap.add_argument('--out', help='落盘路径；缺省只打印统计')
    ap.add_argument('--list', action='store_true', help='列出全部命中块，不落盘')
    ap.add_argument('--index', type=int, default=0, help='命中多个块时取第几个（从 0 起；给了 --expect-md5 则自动按 md5 选）')
    ap.add_argument('--expect-md5', help='期望 md5（全串或前缀）；两种口径（含/不含行尾）任一匹配即可')
    ap.add_argument('--expect-chars', type=int, help='期望字符数（按块体原样，不含行尾）')
    ap.add_argument('--py-compile', action='store_true', help='落盘后 py_compile 校验')
    args, _ = ap.parse_known_args()

    text = open(args.file, encoding='utf-8').read()
    blocks = find_blocks(text, args.sig)

    if not blocks:
        print(f"[FAIL] 未找到含签名 [{args.sig}] 的代码块")
        sys.exit(1)

    # 多块 + 给了期望 md5 → 自动按 md5 筛选
    if len(blocks) > 1 and args.expect_md5:
        hits = [b for b in blocks if md5_match(b[0], args.expect_md5)]
        if len(hits) == 1:
            blocks = hits
            print(f"[选择] 按 expect-md5 自动选中 1 个匹配块")
        elif len(hits) > 1:
            print(f"[FAIL] 有 {len(hits)} 个块都匹配 expect-md5，请用 --index 指定")
            sys.exit(1)
        # 0 个命中：走后面的统一断言报错路径

    if args.list:
        for k, (b, ln, style) in enumerate(blocks):
            print(f"[{k}] 行{ln} {style}闭栏 {len(b)} 字符 md5={md5_of(b)[:12]}…(块体) / {md5_of(b + chr(10))[:12]}…(含行尾) 首行: {b.splitlines()[0][:56] if b else ''}")
        print(f"共 {len(blocks)} 个候选块")
        sys.exit(0)

    if len(blocks) > 1:
        print(f"[提示] 命中 {len(blocks)} 个块，用 --index 选择或 --list 查看：")
        for k, (b, ln, style) in enumerate(blocks):
            print(f"  [{k}] 行{ln} {len(b)} 字符 首行: {b.splitlines()[0][:56] if b else ''}")

    block, ln, style = blocks[min(args.index, len(blocks) - 1)]
    m_raw, m_nl = md5_of(block), md5_of(block + '\n')
    print(f"[提取] 行{ln} {style}闭栏 {len(block)} 字符 md5={m_raw[:12]}…(块体) / {m_nl[:12]}…(含行尾)")

    # 断言（md5 双口径任一匹配；字符数按块体原样）
    ok = True
    if args.expect_chars is not None and len(block) != args.expect_chars:
        print(f"[FAIL] 字符数 {len(block)} != 期望 {args.expect_chars}")
        ok = False
    if args.expect_md5 and not md5_match(block, args.expect_md5):
        print(f"[FAIL] md5（两种口径）均不匹配期望 {args.expect_md5}")
        ok = False
    if not ok:
        print('FENCE_EXTRACT_MISMATCH —— 已中止落盘，先核对（勿带病覆盖）')
        sys.exit(1)

    if args.out:
        # 落盘：canonical 口径 = 块体 + 行尾换行（与 r2 交接文档一致）
        with open(args.out, 'w', encoding='utf-8') as f:
            f.write(block + '\n')
        print(f"[PASS] 已落盘 {args.out}（{len(block) + 1} 字节，含行尾）")
        if args.py_compile and args.out.endswith('.py'):
            try:
                py_compile.compile(args.out, doraise=True)
                print(f"[PASS] py_compile 通过")
            except py_compile.PyCompileError as e:
                print(f"[FAIL] py_compile 失败: {e}")
                sys.exit(1)
    print('FENCE_EXTRACT_OK')
    sys.exit(0)

if __name__ == '__main__':
    main()
