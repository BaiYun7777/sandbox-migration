---
name: sandbox-migration
description: 沙箱迁移/新对话环境恢复 SOP（2026-10-17 全程实跑固化为脚本）。当用户换新沙箱、新对话、或本地环境重置后需要恢复「任务端 prompt + 资料库 + skill 实体」工作环境时使用——涵盖在线状态自检、资料库文档读取、内嵌脚本提取、本地存档重建、需求单登记、交接包还原、端到端验证。内置足彩推荐系统项目资产地图（任务 #4539406/#6600221、节点 ID、md5 基线）。
---

# Sandbox Migration · 沙箱迁移恢复 SOP

> 本 skill 由 2026-10-17 沙箱迁移全程实跑固化：三个可执行脚本 + 三份 references（资产地图 / 需求单模板 / 迁移复盘）。新对话开局按本 SOP 走，无需向用户逐步来回问。

## 0. 定位与触发

- **触发场景**：用户说「换新对话/新沙箱/环境重置了/迁移/恢复环境」，或开局发现本地存档、skill 实体缺失。
- **三位一体**：任务端 prompt（唯一准绳）+ 资料库（交接文档/需求单/交接包）+ skill 实体（本地承载与兜底源）。恢复目标 = 三者一致。
- **铁律**：恢复全程**零 PUT**（部署是另一件事，必须有用户明确批复口令「批/改吧」）；`/tmp` 只当草稿，持久产物一律落 `/workspace`；不知道就说不知道。

## 1. 开局三步（先做这三件，再谈别的）

```bash
# ① 在线自检（纯 GET）：两端 md5/字符数 vs 基线 + λ canonical 校验
python3 <skill>/scripts/online_check.py
#    ALL_PASS → 版本未变，走恢复；FAIL → 有人动过线上或版本已推进，先问用户

# ② 找资料库最新交接节点（更新时间最新的优先）：
python3 <library>/space_api.py node-info --node-id <id>        # 验 kind
python3 <library>/doc/get_doc_reviews.py --page-id <id>        # 读全文

# ③ 盘点本地：存档库 + skill 实体在不在、md5 对不对 → 差异分级（可自恢复 / 需交接包 / 需用户）
```

## 2. 完整 SOP（七步）

| 步 | 动作 | 工具 / 指引 |
|---|---|---|
| 1 | 在线自检定版本 | `scripts/online_check.py`（基线在脚本 CONFIG 块，换版本先改它） |
| 2 | 读资料库交接文档与最新节点 | 工具链命令见 `references/资产地图_足彩推荐系统.md` §五 |
| 3 | 盘点本地差异并分级 | 对照资产地图 §四本地结构逐项核 md5 |
| 4 | 自恢复：从在线 prompt fence 提取内嵌脚本 | `scripts/fence_extract.py`（已内置行内闭合/多块两个坑的处理） |
| 5 | 交接包还原（若有） | `scripts/pkg_restore.py --manifest <json>`：取链→下载→md5→解压到 /tmp，**落位人工确认**（脚本只打印提示，不碰 /workspace） |
| 6 | 三层验证 | ① online_check 复跑 ② 原环境 build 脚本端到端重建复现 ③ 实测版互证（guard 类） |
| 7 | 文档层收尾 | README/SKILL/CHANGELOG 更新、需求单总结终态、用户决策记录归档 |

## 3. 脚本清单（scripts/，均为 2026-10-17 实跑固化）

| 脚本 | 用途 | 安全边界 |
|---|---|---|
| `online_check.py` | 任务端在线状态自检（基线可配置） | 纯 GET，零写入零 PUT |
| `pkg_restore.py` | 交接包下载/校验/解压 + 落位提示 | 只写 /tmp，落位人工确认 |
| `fence_extract.py` | prompt 内嵌代码块按签名提取 + md5 断言 | 只读输入文件，落盘前断言不符即中止 |

### 3.1 自身文件台账（2026-10-18 15:4x 重算 · 453 r4 / 660 r22 部署后）

| 文件 | 字符数 | md5 |
|---|---|---|
| `SKILL.md` | 8,100 | —（自指：文件无法嵌自身 md5，改后本行字符数随之刷新；实体完整性以其余 6 件 + 本表存在性交叉判断） |
| `scripts/online_check.py` | 9,058 | `6ebaaa4d40990f2e21c073cec0696ade` |
| `scripts/pkg_restore.py` | 4,856 | `2d62e5946edee23ff62f3e0a814d397d` |
| `scripts/fence_extract.py` | 6,484 | `b038d1be8287f3fccd2840b568a176a3` |
| `references/资产地图_足彩推荐系统.md` | 6,868 | `62a9feb29c9baa08291bbb09b3470081` |
| `references/需求单模板.md` | 2,769 | `c84c8d25e6165ef9cb02d204d4d398e1` |
| `references/迁移复盘_20261017.md` | 4,959 | `2e5207befc2f6aced25ebdd52c73c9d4` |

> 维护纪律：**每次编辑本 skill 任一文件后重算本表**（`md5sum` + `wc -c`，`__pycache__` 不计）；迁移验收时用本表核对 skill 实体完整性，缺一项即按差异分级处理。10-17 旧台账（SKILL.md `877227725d27…`、online_check.py `14a6411bd942…` 等）随本次 10-18 更新作废；10-18 上午旧台账（SKILL.md 7,791 / online_check.py `88f09020…` / 资产地图 `e6e00b8e…`）随 r4/r22 部署同步作废。另：453/660 每次部署归档后也须重算本表并同步 §4 基线行 / online_check.py / 资产地图（部署 SOP 收尾四件，见 football-prediction SKILL.md §0 铁律段）。

## 4. 足彩推荐系统专属速查

- 任务端：#4539406（11:05 推荐）/ #6600221（08:00 复盘）；API `http://auth.proxy/codebuddy/v2/as/scheduler/tasks/<id>`，prompt 在 `['data']['agentConfig']['prompt']`。
- 当前基线（2026-10-18 15:4x）：453 = v4.0.0-r4 · 235,891 / `6c9af0ce…`；660 = v4.0.0-r22 · 256,311 / `820aa981…`；余量：453 = 23,914 / 660 = 3,494 / 上限 259,805。历史链：453 r1 230,467 → r2 231,611 → r3 232,375 → **r4 235,891（候选窗口改革+P0/P1/P2 修复）**；660 r1 248,159 → r2（含 10-17 桥接）251,382 → r20 256,852 → r21 257,605 → **r22 256,311（13:55 批入账+行数归正 406+瘦身 −1,294）**。
- **部署后同步义务（2026-10-18 起，用户批复「同意你的建议」固化）**：453/660 任一部署归档后，本 skill 四处必须同步——① `scripts/online_check.py` CONFIG 块（TASKS + ARCHIVE）② 本文件 §4 基线行 ③ `references/资产地图_足彩推荐系统.md` 时点快照表 ④ 本文件 §3.1 台账。该动作已写入 football-prediction SKILL.md §0 部署 SOP 铁律收尾段；不同步 = 开局自检拿过期基线误判 FAIL 或按错误版本恢复。
- λ canonical：`football-prediction/scripts/lambda-source.py`（49,546 / `19c322ce…`）是唯一 canonical，两端内嵌块由它单向同步。
- 完整节点 ID / 包 md5 / 本地树：`references/资产地图_足彩推荐系统.md`（**时点快照，换版本先核**）。
- 需求单结构、批复口令含义、上库方法：`references/需求单模板.md`。

## 5. 高频坑速查（详见 `references/迁移复盘_20261017.md`）

1. 上传附件 / `/space/d/` 链接读出 HTML 空壳 → 一律走 library 脚本通道，禁 WebFetch；
2. fence 提取：行内闭合 ``` 与围栏头复用两个坑 → 用 `scripts/fence_extract.py`；
3. **λ 块定位不可用标题行 hint**：prompt 里多处含 `lambda-source.py` 字样会框错区间返回空块；且 453 有 3 个块含 `market_lambda` 字样，签名不唯一 → 必须**全量扫块 + canonical md5 筛选**（`online_check.py` 已内置）；
4. `submit_doc_edit.py`：动作字段是 `type`；表格必须 `<Table>` 组件语法整表插入；
5. `cp -r src dest/` 目标同名会嵌套 → 落位前核对目录结构；
6. 包内 README 与本地版本冲突 → diff 后新版为现行、旧版改名留档，向用户说明；
7. 文档计数与实物不符（实测三例：包 B 19↔20 目录、包 D 39↔31 文件、diff 行数口径）→ zip md5 已验时以实物为准并如实汇报。

## 6. 红线（迁移全程必守，违反 = 事故）

1. 决策权归用户：恢复方案先汇报再动手；报告纯陈述，禁决策性字样。
2. 任务更新后必须问用户是否跑验证，禁止自作主张运行验证任务。
3. 全程零 PUT；部署须用户批复口令（「批 / 改吧 / 1，改吧」= 部署；「同步。明天再跑」= 今天不动；「不干了」= 永久关闭不再问）。
4. skill 安装先过安全检查；NXP 账户/邮箱/密码绝对禁区。
5. 代码引用必须同时显示名称；简体中文；表格/加粗优先。
6. 补账必须一次补完，严禁分批挤补。
