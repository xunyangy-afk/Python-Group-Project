# 七巨头数据清洗整合

为初级股票研究分析师准备 AAPL、AMZN、GOOGL、META、MSFT、NVDA、TSLA 的比较数据，支持后续根据价格表现、波动率、成交量、新闻与财报选择值得深入研究的 1–2 只股票。本次提供清洗和必要验证，不包含完整 Dashboard。

六分支代码、Notebook 与验证记录的比较、规则来源和待确认事项见 [CLEANING_DECISIONS.md](CLEANING_DECISIONS.md)。规则尚未获得组员确认的地方均标为建议。

## 完整运行命令

在仓库根目录使用 Python 3.13。安装依赖后，一条命令完成关键风险测试、两次新进程全量清洗、原始哈希核对和输出可复现性检查：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe verify_cleaning.py
```

macOS/Linux 对应使用 `.venv/bin/python`。只运行清洗时使用 `python -m team_cleaning`；可传 `--raw-dir sources/raw --output-dir artifacts`，输入仍必须符合 sources/manifest.json 的固定 SHA。换快照需先建立新的来源清单、审查规则并重新验证，不应跳过哈希检查。错误会返回非零退出码，不要把旧 artifacts 当失败运行的新结果。

本次实测 Python 3.13.15、pandas 3.0.1、numpy 2.3.5、pyarrow 25.0.0。requirements.txt 固定直接及传递依赖。没有运行时安装或自动替换原始数据的行为。

## 来源与可提交文件

来源：[TheFinAI/Herculean](https://huggingface.co/datasets/TheFinAI/Herculean)，TheFinAI / Xueqing Peng，Herculean（成员文档所记归属）。原有 data/ 文件未改动；完整字节复制到 sources/raw/，用于克隆后离线复现。版本是 `team-local-sha256-v1`，每文件完整 SHA 和字节数见 [manifest.json](sources/manifest.json)。本地数据与 Zack 清单完整 SHA、Peter 复现 SHA 前缀一致。

**上游 revision/原始下载日期未确认。** Evelyn 记录了另一组 SHA 和上游 revision，不能套用于这些文件。2026-10-18 读取固定版本源 README 返回需要认证，尚未独立确认上游版本及再分发许可。成员文档记载 CC BY 4.0；团队需向有源站权限的成员确认并补充许可材料，再公开发布数据。此事项不影响已完成的本地相同快照运行。

以下三份均为完整正式表，随本地整合提交进入 PR，无50行样本替代：

| 文件 | 行数 | 行含义 / 键 |
|---|---:|---|
| [prices_clean.parquet](artifacts/prices_clean.parquet) | 2,324 | 公司日期行情；id 与 symbol/date 唯一 |
| [news_clean.parquet](artifacts/news_clean.parquet) | 3,402 | 公司日新闻摘要；表内 id 唯一；同日事件允许保留 |
| [filings_clean.parquet](artifacts/filings_clean.parquet) | 63 | 财报文档及节选；表内 id 唯一；业务键候选 symbol/date/document_type |

三正式表合计约 6.13 MB，最大 news 文件约 5.37 MB；原始三文件合计约 5.88 MB。普通 Git 可以容纳，本次不需 LFS。正式表、原始快照与排除记录均显式保留在 Git；`.gitignore` 仅忽略已有本地 data/、cleaning_outputs/、虚拟环境和审查临时文件。

若未来多快照增长明显，建议将原始快照改为受权限控制的版本化对象存储，以 manifest 中不可变地址及 SHA 下载；较大的正式 Parquet 改用 Git LFS 并配置 `.gitattributes` 和 CI 拉取验证。不要以抽样 CSV 替代完整正式交付。

## 输出与规则

`team_cleaning/pipeline.py` 负责加载、规范类型、范围筛选、文本格式处理、异常标记、排除审计、独立保存及连接验证。`team_cleaning/analysis.py` 单独提供按日期范围计算的分析函数；清洗价格表不混入预计算的标准化价格、收益或波动率。

- symbol/form trim + upper；日期保持原日历日期，统一为无时区 datetime64[ns]；价格 float64、成交量 Int64、ID string；稳定排序。
- ADBE 全部保存在 `artifacts/excluded_*.parquet`，附 `_reason` 和零起算 `_source_row`。原始版本与来源行可精确追溯。
- 完全重复与主键冲突分别计数、解释和审计；不按重复文本删除财报。正式价格冲突整组隔离；同日不同事件先保留、标记再聚合连接。
- 财报一次 HTML 解码和首尾空白清理，保留段落、原标点和内部空白。新闻仅首尾清理；真实缺失保持缺失。
- 大幅价格变化、可疑新闻、短风险节选和重复风险文本保留并标记。阈值为建议，见决策文档。
- 三张表独立；仅验证同日事件计数连接，使用 `validate` 防止放大，未匹配事件键另存。没有输出预测面板，也没有声称下一交易日映射能消除信息泄漏。

`artifacts/validation_report.json` 包含来源、环境、所有列缺失值/类型转换、重复数量、排除理由、标记计数、数值范围、成交量对账、连接结果和输出 SHA。`coverage.csv` 为分公司日期覆盖；`text_changes.csv` 给出变化来源行、规则和前后文本 SHA；全文可由原始及正式 Parquet 恢复。`verification.json` / `.md` 记录测试日志和新进程复跑证据。

## 实际验证结果

| 表 | 原始 | ADBE 排除 | 其他排除 | 正式 |
|---|---:|---:|---:|---:|
| prices | 2,656 | 332 | 0 | 2,324 |
| news | 3,888 | 486 | 0 | 3,402 |
| filings | 73 | 10 | 0 | 63 |

数量自然等于历史核对目标，代码没有强制删增以匹配。原始字段清洗前后无缺失值；完全重复、重复 ID、价格业务键冲突、数值域及 OHLC 异常均为0。13,944 个保留价格/成交量数值逐值精确相同；总成交量 159,456,800,900 = 保留 158,002,379,300 + ADBE 1,454,421,600。完整来源的146个财报文本单元完成解码/边界清理，其中正式保留表126个、ADBE排除表20个。

价格覆盖 2024-12-02–2026-03-31（每家公司332条）；新闻覆盖 2024-12-01–2026-03-31（每家486条）；财报整体 2024-01-26–2026-02-25（每家9条，具体起止见 coverage.csv）。7 条 >12% 价格变动、7 条占位/短新闻、1 条疑似截断新闻、9 条短风险文本、7 条重复上一风险文本保留并标记。全部新闻标记时间可用性未核验；未来日期检测0命中不能证明无泄漏。

两次事件聚合连接均保持2,324行，所有价格字段精确不变；1,078条新闻和28条财报没有同日行情，已保留。2,317个可计算的 adj_close 收益与独立 Decimal 比值核对，7个首观测收益为缺失。11项关键风险测试及两次新进程完整运行已通过；所有12个生成文件逐字节相同，包括正式表、排除表和验证报告。详见 [实际报告](artifacts/validation_report.md) 与 [复现记录](artifacts/verification.md)。

## 分析接口示例

```python
import pandas as pd
from team_cleaning.analysis import interval_metrics

prices = pd.read_parquet("artifacts/prices_clean.parquet")
series, metrics = interval_metrics(prices, "2025-01-01", "2025-06-30")
```

日期闭区间内先筛选再计算；normalized_price 基于区间内第一条真实观测，基数100；收益只用 adj_close 且 `pct_change(fill_method=None)`。不跨区间左边界、不跳过缺失端点来选基数、不前向填充；波动率使用有效收益样本标准差 ddof=1，不足两个收益为缺失。有效成交量才进入均量。这些计算接口没有扩展为 Dashboard。

待确认事项：启发式阈值、冲突治理、区间指标口径、来源 revision/许可、事件发布日期含义及复权方法。交易所日历和新闻事实未独立验证；相关限制在决策记录和机器报告中明确列出。
