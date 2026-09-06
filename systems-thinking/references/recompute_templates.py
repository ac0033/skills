"""
白盒讲解员 · 复算模板库
========================
用途：讲解数据科学/ML 项目时，把报告里的"二手结论数字"还原成"用户能自己重算的一手计算"。
用法：每个函数都接受 pandas DataFrame / numpy 数组，改一下列名和数据源就能套到你的项目上。

设计标准（每个模板都遵守）：
  1. 列出参与计算的原始值
  2. 公式逐个符号解释（写在 docstring 里）
  3. 代入真实数手算一遍
  4. 随机/迭代过程打印前几次中间值（让用户看见"它真的在跑"）
  5. 返回结果，便于和落盘 CSV/JSON 的值比对

依赖：numpy, pandas
"""
import numpy as np
import pandas as pd


# =============================================================================
# 模板 1：paired bootstrap 置信区间
# 场景：只有 N 个月/N 个独立单元的差值，想知道"中位优势的可能范围"，判断是否显著。
# 为什么不用 t 检验：相邻月相关、差值分布偏斜；bootstrap 不假设分布形态，更稳。
# =============================================================================
def paired_bootstrap_ci(diffs: np.ndarray, n_boot: int = 2000,
                        seed: int = 42, verbose: bool = True) -> dict:
    """
    配对自助抽样 95% 置信区间。

    参数
    ----
    diffs : 长度为 N 的一维数组，每个元素 = 某单元上 (模型指标 - 基线指标) 的差值。
            必须是"配对差值"——同一单元的模型和基线在同一分母上比，先逐单元算差再抽样。
    n_boot : 重抽样次数，默认 2000。
    seed   : 随机种子，保证可复现。

    原理（逐个符号）
    ----------------
    设观测差值 d_1 ... d_N，观测中位数 m_obs = median(d)。
    我们想知道"如果换一批 N 个单元，中位数大概落在哪"。
    做法：有放回地从 {d_1...d_N} 抽 N 个 → 算这一个重抽样样本的中位数；
         重复 n_boot 次 → 得到 n_boot 个中位数；
         取这 n_boot 个中位数的 2.5% 和 97.5% 分位 → 95% CI = [lo, hi]。
    判读：CI 不含 0 → 差异统计显著；CI 跨 0 → 不能说有显著差异。

    返回
    ----
    dict: observed_median, ci_lo, ci_hi, significant(布尔), first_samples(前5次中间值)
    """
    rng = np.random.default_rng(seed)
    diffs = np.asarray(diffs, dtype=float)
    m = len(diffs)
    observed_median = float(np.median(diffs))

    samples = np.empty(n_boot)
    first_samples = []  # 存前 5 次，用于讲解时展示"中间迭代"
    for i in range(n_boot):
        idx = rng.integers(0, m, size=m)        # 有放回抽 N 个（同一单元可重复/可缺席）
        med_i = float(np.median(diffs[idx]))
        samples[i] = med_i
        if i < 5 and verbose:
            print(f"  重抽样{i+1}: 抽到索引 {idx.tolist()} -> 中位数 = {med_i:+.4f}")

    lo, hi = np.percentile(samples, [2.5, 97.5])
    significant = (lo > 0) or (hi < 0)          # 区间不跨 0 即显著

    if verbose:
        print(f"观测中位数 = {observed_median:+.4f}")
        print(f"95% CI = [{lo:.4f}, {hi:.4f}]  ->  {'显著(不含0)' if significant else '不显著(跨0)'}")

    return {"observed_median": observed_median, "ci_lo": float(lo), "ci_hi": float(hi),
            "significant": bool(significant), "first_samples": first_samples}


# =============================================================================
# 模板 2：按月 Top-K 覆盖率
# 场景：运营只关心"头部选得准不准"。每月按预测分取前 K，看覆盖了多少真实成交额。
# =============================================================================
def topk_coverage(y_true: np.ndarray, score: np.ndarray, K: int,
                  verbose: bool = True) -> float:
    """
    Top-K 覆盖率 cov_topk。

    参数
    ----
    y_true : 该月每个商品的【真实】成交金额（一维，长度 = 商品数）。
    score  : 该月每个商品的【预测/打分】值（与 y_true 同序、同长度）。
    K      : 取前几名。

    公式（逐个符号）
    ----------------
    act_idx = 按 y_true 降序的前 K 个索引      # 真实世界的 Top-K 是哪些商品
    act     = y_true[act_idx].sum()            # 真实 Top-K 的总金额（分母）
    idx     = 按 score 降序的前 K 个索引        # 模型挑出的 Top-K 是哪些商品
    covered = y_true[idx].sum()                # 模型挑的这些商品，实际卖了多少（分子）
    cov_topk = covered / act                   # 模型抓住了真实头部的百分之多少

    注意：分子用的是 y_true[idx]（模型选中商品的【真实】金额），不是 score[idx]。
         这是"用真实答案检验模型排序"，不是"用预测值自夸"。
    """
    y_true = np.asarray(y_true, dtype=float)
    score = np.asarray(score, dtype=float)
    assert len(y_true) == len(score), "y_true 和 score 必须等长（同一批商品）"

    act_idx = np.argsort(y_true, kind="stable")[::-1][:K]   # 真实 Top-K
    act = y_true[act_idx].sum()                              # 分母
    idx = np.argsort(score, kind="stable")[::-1][:K]         # 模型 Top-K
    covered = y_true[idx].sum()                              # 分子

    cov = covered / act if act > 0 else float("nan")
    if verbose:
        print(f"K={K}: 真实Top-{K}金额(分母)={act:,.0f}, "
              f"模型Top-{K}实际金额(分子)={covered:,.0f}, 覆盖率={cov:.4f}")
    return float(cov)


def win_loss_tie(model_cov: np.ndarray, base_cov: np.ndarray) -> dict:
    """
    胜平负统计：逐月比较模型 vs 基线的覆盖率。
    model_cov / base_cov : 长度 = 月数 的覆盖率数组（同序）。
    规则：diff>0 胜，diff<0 负，diff==0 平。
    """
    diff = np.asarray(model_cov) - np.asarray(base_cov)
    win = int((diff > 0).sum())
    loss = int((diff < 0).sum())
    tie = int((diff == 0).sum())
    return {"win": win, "loss": loss, "tie": tie,
            "diff_median": float(np.median(diff)), "diffs": diff.tolist()}


# =============================================================================
# 模板 3：价值分层 + 下月迁移矩阵
# 场景：每月按预测分把商品切 A/B/C/D 层，再看相邻月各层怎么流动、稳不稳定。
# =============================================================================
def value_layer(rank_pct: float) -> str:
    """百分位 rank -> 价值层。rank>=0.95 A；>=0.80 B；>=0.50 C；否则 D。"""
    if rank_pct >= 0.95: return "A"
    if rank_pct >= 0.80: return "B"
    if rank_pct >= 0.50: return "C"
    return "D"


def stratify_month(pred_df: pd.DataFrame, score_col: str = "pred_expected",
                   fold_col: str = "fold") -> pd.DataFrame:
    """
    对单月（或整表按 fold 分组）按预测分排名 -> 百分位 -> 价值层。
    关键：每月独立排名（groupby fold），不跨月混排——因为每月候选集合和量级不同。
    """
    out = pred_df.copy()
    out["_rank"] = out.groupby(fold_col)[score_col].rank(pct=True)
    out["value_layer"] = out["_rank"].map(value_layer)
    return out


def transition_matrix(layer_t: pd.DataFrame, layer_t1: pd.DataFrame,
                      key: str = "商品名称",
                      layer_col: str = "value_layer",
                      active_col: str = "active_t",
                      amt_col: str = "eff_amt_t") -> pd.DataFrame:
    """
    相邻两月的分层迁移矩阵。
    layer_t / layer_t1 : 上月 / 下月的分层表（都含 key, layer_col, active_col, amt_col）。
    返回：from->to 的人数 n、下月活跃率、下月金额。对角项远大于非对角 = 分层稳定。
    """
    m = layer_t.merge(layer_t1, on=key, suffixes=("_t", "_t1"))
    g = (m.groupby([layer_col + "_t", layer_col + "_t1"])
           .agg(n=(key, "size"),
                next_active=(active_col + "_t1", "sum"),
                next_amt=(amt_col + "_t1", "sum")))
    g["next_active_rate"] = g["next_active"] / g["n"]
    return g.reset_index().rename(columns={layer_col+"_t": "from", layer_col+"_t1": "to"})


# =============================================================================
# 模板 4：分数加权集中度 proxy
# 场景：清单里每个商品有个"供应商集中度" s_i，用预测分 w_i 加权平均，看清单整体是否过度依赖单一供应商。
# =============================================================================
def weighted_concentration_proxy(weights: np.ndarray, shares: np.ndarray,
                                 valid: np.ndarray = None,
                                 verbose: bool = True) -> float:
    """
    分数加权集中度 proxy。

    参数
    ----
    weights : 每个商品的预测分 w_i（如 pred_expected）。
    shares  : 每个商品的供应商集中度 s_i（如 top_sup_share，0~1，越大越依赖单一供应商）。
    valid   : 布尔掩码，标记"有供应商份额数据"的行；None 则全部参与。

    公式（逐个符号）
    ----------------
    proxy = sum(w_i * s_i) / sum(w_i)   ，只对 valid=True 且 w_i 有效的行求和。
    含义：高分商品权重大——清单越是把宝押在"高集中度"的高分商品上，proxy 越接近 1。
    判读：proxy 接近上限（如 0.99）才触发剔除；远低于上限说明高价值商品多为多家供货。
    """
    w = np.asarray(weights, dtype=float)
    s = np.asarray(shares, dtype=float)
    if valid is None:
        valid = np.isfinite(w) & np.isfinite(s)
    else:
        valid = np.asarray(valid, dtype=bool) & np.isfinite(w) & np.isfinite(s)

    wv, sv = w[valid], s[valid]
    denom = wv.sum()
    proxy = float((wv * sv).sum() / denom) if denom > 0 else float("nan")

    if verbose and len(wv) >= 2:
        # 打印前两行的加权过程，让用户看见"怎么加出来的"
        contrib = wv[:2] * sv[:2]
        print(f"  前2行加权演示: "
              f"({wv[0]:,.1f}×{sv[0]:.4f} + {wv[1]:,.1f}×{sv[1]:.4f}) / "
              f"({wv[0]:,.1f}+{wv[1]:,.1f}) = {contrib.sum()/wv[:2].sum():.4f}")
        print(f"  全部 {int(valid.sum())} 行算完 -> proxy = {proxy:.4f}")
    return proxy


# =============================================================================
# 自检：用一组玩具数据跑一遍，确认模板可用（讲解时可当场运行给用户看）
# =============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("模板 1：paired bootstrap CI")
    print("=" * 60)
    diffs = np.array([0.0235, 0.0237, 0.0281, 0.0236, 0.0669, 0.0345,
                      -0.0212, 0.0615, 0.0509, 0.0151, 0.0416, 0.0357])
    paired_bootstrap_ci(diffs)

    print("\n" + "=" * 60)
    print("模板 2：Top-K 覆盖率")
    print("=" * 60)
    y_true = np.array([100, 80, 60, 40, 20])
    score_model = np.array([100, 60, 80, 40, 20])  # 模型把 80 和 60 的顺序排反了
    topk_coverage(y_true, score_model, K=3)
    # 手算核对：真实Top3=100+80+60=240；模型选3个(100,60,80对应真实值100,60,80)=240?
    # 模型按score取前3索引=[0,2,1]->真实值[100,60,80]=240 -> cov=1.0（此例碰巧选对了集合）

    print("\n" + "=" * 60)
    print("模板 4：集中度 proxy")
    print("=" * 60)
    weighted_concentration_proxy(
        weights=np.array([4_036_017.5, 3_415_231.5, 1_000_000.0]),
        shares=np.array([0.544613, 0.168898, 0.30]))
