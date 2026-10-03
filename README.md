# Wishclaim · 礼物愿望认领

发布 → 认领锁定（互斥+TTL）→ 核销/释放。

凑份子赞助：愿望可设 `target_amount`；他人 chip-in 分轨记账。
预览（`chipin/preview`）返回累计/缺口但不落库，确认（`chipin/confirm`）后累加。
未凑满目标无法核销且保持 claimed；达标方可核销，核销时钉住累计快照。
目标金额仅未认领可改，认领瞬间快照、之后不回刷。单笔赞助必须 > 0。
认领与赞助分轨，同一人允许既认领又赞助。

| 服务 | 端口 |
| --- | --- |
| 前端 | 5200 |
| API | 10200 |

```bash
docker compose up --build
pytest backend/app/tests
```

- 模块：`chipin_ledger`（赞助账本）/ `chipin_progress`（进度投影）/ `fulfill_gate`（核销门禁）。
- 0-1：`wish_comment` / `secret_santa` / `price_cap`。
