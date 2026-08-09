# FinMamba 官方模型接入

本站使用作者仓库 <https://github.com/TROUBADOUR000/FinMamba> 的提交
`e4f8ce33e4ddbc4a46b738de9265771aec2c4d16`，许可证为 Apache-2.0。
模型网络、损失函数和训练器不做结构修改；本站代码只负责日频沪深300数据契约转换、
训练命令编排、最新截面推理产物转换和网页模型选择。

## 数据口径

- 输入严格使用论文列出的 `high / low / open / close / volume / turnover` 六个日频字段。
- 标签是下一交易日收盘收益率 `(close[t+1] / close[t]) - 1`。
- 时间窗口为作者默认的 20 个交易日。
- 动态关系图由作者 `genRelation.py` 生成：逐特征 20 日 Spearman 相关，再乘行业衰减矩阵。
- 为满足作者固定股票张量要求，选取当前沪深300中覆盖本地全部历史日期的稳定股票集合；
  这与论文 CSI300 实验只保留 285 个完整节点的做法一致。
- 当前行情源的行业列尚无真实分类时，未知行业之间采用论文“不同产业”衰减值 0.1，
  并在 manifest 与网页状态中明确披露。

## 运行

先在任意平台准备作者输入文件和查看环境状态：

```powershell
.\.venv\Scripts\python.exe scripts\train_finmamba_official.py
```

实际训练必须放在安装了 NVIDIA CUDA 的 Linux 环境中，因为作者依赖的官方
`mamba-ssm` 不支持本站当前 Windows CPU 运行环境：

```bash
python -m venv .venv-linux
source .venv-linux/bin/activate
python -m pip install --upgrade pip
python -m pip install -r third_party/FinMamba/requirements.txt
python scripts/train_finmamba_official.py --train --device cuda:0 --epochs 5
```

成功后会生成：

- `models/checkpoints/finmamba_current_csi300/best_model.pth`
- `reports/research_loop/finmamba_predictions.parquet`
- `reports/research_loop/finmamba_predictions_report.json`

`/api/scores?model=finmamba` 和 `/scores?model=finmamba` 会自动读取上述产物。
没有 checkpoint 时，页面仍可选择 FinMamba 查看准确的运行阻塞原因，但不会展示伪造预测。
网站的日频增量流水线也包含该训练入口：数据指纹不变时跳过；数据变化后，兼容的
Linux+CUDA 环境会重训并发布，当前 Windows CPU 环境只刷新输入与阻塞状态，不影响其他模型更新。
