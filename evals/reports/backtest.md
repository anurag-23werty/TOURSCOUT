# Backtest: real tours vs TourScout's demand ranking

12 artists. For each, the metros from their most recent real tour (setlist.fm, ≥ 6 cities in one country and year) are compared with three rankings of the same candidate metros: TourScout's demand score (Qloo heatmap, no reach data), population, and random. Recall@N = share of the played metros in the top N.

| Ranking | Recall@10 | Recall@25 |
|---|---|---|
| **TourScout demand** | **42%** | **63%** |
| Population only | 34% | 60% |
| Random | 1% | 4% |

| Artist | Tour year | Metros played | TS@10 | Pop@10 | TS@25 | Pop@25 |
|---|---|---|---|---|---|---|
| Hovvdy | 2026 | 15 | 40% | 33% | 67% | 73% |
| Men I Trust | 2026 | 8 | 25% | 12% | 50% | 25% |
| Slow Pulp | 2026 | 11 | 55% | 46% | 82% | 82% |
| Pinegrove | 2022 | 29 | 28% | 24% | 38% | 41% |
| Snail Mail | 2026 | 42 | 24% | 21% | 43% | 43% |
| Faye Webster | 2026 | 11 | 46% | 55% | 82% | 73% |
| Hana Vu | 2025 | 14 | 29% | 14% | 43% | 50% |
| Thee Sacred Souls | 2026 | 20 | 35% | 45% | 75% | 70% |
| Alvvays | 2025 | 11 | 36% | 36% | 55% | 55% |
| Japanese Breakfast | 2026 | 9 | 33% | 22% | 56% | 56% |
| Divino Niño | 2023 | 6 | 50% | 33% | 67% | 50% |
| Cassandra Jenkins | 2024 | 8 | 100% | 62% | 100% | 100% |

**Caveats.** A real tour is not the optimal tour (routing, offers and luck shape it), so this measures signal, not ground truth. Qloo's taste data is current, and touring a city can itself create fans there, so some agreement may run in the other direction. Population is a strong baseline because big cities get most shows; TourScout's job is the mid-sized cities population misses.
