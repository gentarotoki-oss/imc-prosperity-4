"""
Round 3 Manual Trading — B2 シミュレーション

設定:
  - reserve ∈ {670, 675, ..., 920}, 51 点に均等分布
  - b1 = 796 固定 (strict 不等号 + 5刻み境界の最適)
  - b2 で追加で取れる reserves: (796, b2] ∩ {800, 805, ...}
  - ペナルティ: b2 <= avg_b2 のとき ((920-avg_b2)/(920-b2))^3

評価:
  1) avg_b2 を固定して EV(b2) カーブ
  2) 他プレイヤー分布を仮定してナッシュ的探索
  3) ベスト・レスポンス反復で均衡を求める
"""
import numpy as np


B1 = 796
RESERVES = np.arange(670, 921, 5)        # 51点
FAIR = 920


def trades_b1(b1):
    """b1 で約定する reserves (strict: b1 > reserve)"""
    return RESERVES[RESERVES < b1]


def trades_b2_extra(b1, b2):
    """b2 で追加約定する reserves: (b1, b2] のうち 5刻み点"""
    return RESERVES[(RESERVES >= b1) & (RESERVES < b2)]


def penalty(b2, avg_b2):
    if b2 > avg_b2:
        return 1.0
    if b2 == avg_b2:
        return 1.0  # 境界扱い、controversial だが甘めに
    # b2 < avg_b2
    return ((FAIR - avg_b2) / (FAIR - b2)) ** 3


def ev_total(b1, b2, avg_b2):
    n1 = len(trades_b1(b1))
    n2 = len(trades_b2_extra(b1, b2))
    pen = penalty(b2, avg_b2)
    return n1 * (FAIR - b1) + n2 * (FAIR - b2) * pen


def ev_b2_only(b1, b2, avg_b2):
    n2 = len(trades_b2_extra(b1, b2))
    pen = penalty(b2, avg_b2)
    return n2 * (FAIR - b2) * pen


# ====================================================================
# 1) avg_b2 を変えたとき、最適 b2 がどう動くか
# ====================================================================
print("=" * 70)
print("[1] avg_b2 別 最適 b2 (b1=796 固定)")
print("=" * 70)
print(f"{'avg_b2':>8} | {'best_b2':>8} | {'EV(b2)':>10} | {'penalty':>8}")
print("-" * 70)

b2_grid = np.arange(797, 921)            # 全整数
for avg in range(820, 871, 5):
    evs = [ev_b2_only(B1, b2, avg) for b2 in b2_grid]
    best_idx = int(np.argmax(evs))
    best_b2 = int(b2_grid[best_idx])
    print(f"{avg:>8} | {best_b2:>8} | {evs[best_idx]:>10.1f} | {penalty(best_b2, avg):>8.3f}")


# ====================================================================
# 2) avg_b2 = 自分以外の bid 平均と仮定して、
#    具体的な b2 候補について「他全員が X を出した場合の EV」を見る
# ====================================================================
print()
print("=" * 70)
print("[2] 他全員が同じ b2=X を出すと仮定したときの自分の EV(b2_self)")
print("=" * 70)
print(f"{'others_b2':>10} | best_b2 | EV(b2)  | best vs follow")
print("-" * 70)
for others in [830, 840, 845, 850, 855, 856, 860, 865, 870]:
    evs = [ev_b2_only(B1, b2, others) for b2 in b2_grid]
    best_idx = int(np.argmax(evs))
    best_b2 = int(b2_grid[best_idx])
    follow_ev = ev_b2_only(B1, others, others)
    print(f"{others:>10} | {best_b2:>7} | {evs[best_idx]:>7.1f} | follow={follow_ev:.1f}")


# ====================================================================
# 3) ベストレスポンス反復 (擬似ナッシュ)
#    全員が前回の avg にベストレスポンスし続ける
# ====================================================================
print()
print("=" * 70)
print("[3] ベストレスポンス反復")
print("=" * 70)

avg = 840.0
for it in range(20):
    evs = [ev_b2_only(B1, b2, avg) for b2 in b2_grid]
    best_b2 = int(b2_grid[int(np.argmax(evs))])
    new_avg = best_b2  # 全員が同じ best response → avg = best_b2
    print(f"iter {it:>2}: avg={avg:>6.1f} -> best_b2={best_b2:>3}, ev={max(evs):>6.1f}")
    if abs(new_avg - avg) < 0.5:
        print(f"  → 収束: b2 = {best_b2}")
        break
    avg = new_avg


# ====================================================================
# 4) avg_b2 と self_b2 の 2D ヒートマップ的サマリ
# ====================================================================
print()
print("=" * 70)
print("[4] EV テーブル: 行=自分のb2, 列=avg_b2")
print("=" * 70)
avgs = [830, 840, 845, 850, 855, 860, 865]
self_b2s = [840, 845, 850, 851, 855, 856, 857, 860, 865]
header = "self\\avg | " + " | ".join(f"{a:>6}" for a in avgs)
print(header)
print("-" * len(header))
for sb in self_b2s:
    row = [ev_b2_only(B1, sb, a) for a in avgs]
    print(f"   {sb:>5} | " + " | ".join(f"{v:>6.1f}" for v in row))


# ====================================================================
# 5) 「他プレイヤーの b2 が分布する」現実的シナリオ
#    Monte Carlo: 100 プレイヤー, 各自の bid は N(mu, sigma) 切り捨て
# ====================================================================
print()
print("=" * 70)
print("[5] Monte Carlo: 他プレイヤー b2 ~ N(mu, sigma), 自分の最適 b2")
print("=" * 70)

rng = np.random.default_rng(42)
N_PLAYERS = 100
N_TRIALS = 5000

for mu, sigma in [(845, 10), (850, 10), (845, 15), (850, 15), (855, 10)]:
    best_b2_for_self = None
    best_ev = -1
    for cand in b2_grid:
        ev_sum = 0.0
        for _ in range(N_TRIALS):
            others = rng.normal(mu, sigma, N_PLAYERS)
            others = np.clip(others, 797, 920)
            avg_incl_self = (others.sum() + cand) / (N_PLAYERS + 1)
            ev_sum += ev_b2_only(B1, int(cand), avg_incl_self)
        ev_avg = ev_sum / N_TRIALS
        if ev_avg > best_ev:
            best_ev = ev_avg
            best_b2_for_self = int(cand)
    print(f"  mu={mu}, sigma={sigma:>2} → best self_b2={best_b2_for_self}, EV={best_ev:.1f}")
