# Sariko Tests

Centralized test suite cho Sariko app. Hai loại test với mục đích khác nhau:

## Cấu trúc

```
tests/
├── smoke/              Manual checklist — chạy qua bằng tay trước mỗi deploy
│   └── DEPLOY_SMOKE_TEST.md
├── backend/            pytest tests cho FastAPI backend (logic + API)
│   ├── pytest.ini
│   ├── conftest.py     sys.path + env stubs
│   ├── requirements.txt
│   ├── unit/           Pure logic, no DB/HTTP
│   └── integration/    FastAPI TestClient + mocked DAOs
├── manual/             Scripts chạy tay (cần real API creds, không auto)
│   ├── test_lalamove_live.py
│   └── check_dev_history.py   DEV: bảng history_* + mật khẩu tối thiểu
└── frontend/           Vitest tests (chưa setup — placeholder)
    └── README.md
```

## Khi nào dùng cái nào

| Trường hợp | Tool |
|---|---|
| **Trước mỗi deploy** | `tests/smoke/DEPLOY_SMOKE_TEST.md` (5-10 phút manual) |
| **Code change cho payment / order / webhook** | Chạy `pytest tests/backend/` (vài giây) |
| **Refactor backend logic** | Add unit test ở `tests/backend/unit/` |
| **Add/change API endpoint** | Add integration test ở `tests/backend/integration/` |
| **Frontend logic phức tạp (composables)** | (TODO) Setup Vitest ở `tests/frontend/` |
| Lỗi lặp (docs/tracking/loi-lap-lai.txt) | test chặn ở tests/backend/unit/test_no_float_money.py, frontend scripts/check-i18n.mjs |

## Setup

### Backend pytest (lần đầu)

```bash
cd backend && pip install -r ../tests/backend/requirements.txt
```

### Chạy backend tests

```bash
# Từ project root
cd tests/backend && pytest

# Hoặc chỉ unit
pytest tests/backend/unit/

# Verbose + show print output
pytest tests/backend/ -v -s

# Chỉ test file/function cụ thể
pytest tests/backend/unit/test_vnpay_signature.py::test_hmac_round_trip
```

### Smoke test

Mở `tests/smoke/DEPLOY_SMOKE_TEST.md` và tick từng item trên browser thật.

### Manual integration scripts

`tests/manual/` chứa script integration cần API thật (Lalamove live, VNPay sandbox).
KHÔNG auto-run, không ảnh hưởng pytest. Chạy thủ công khi cần verify với 3rd party:

```bash
LALAMOVE_MODE=live LALAMOVE_API_KEY=... LALAMOVE_API_SECRET=... \
    python tests/manual/test_lalamove_live.py

# Sau khi deploy DEV: bảng history_*, phí giao server tính, mật khẩu tối thiểu (tài khoản DEV_*)
python3 -I tests/manual/check_dev_history.py
```

## Triết lý

- **Test code logic được sờ thường xuyên** (payment, order state machine, webhook signature) — high ROI.
- **Không test code framework lo** (FastAPI routing, Pydantic validation) — low ROI.
- **Smoke test cho luồng end-to-end** — không thay được automated, nhưng cheap + catch big regressions.
- **Mock DAOs**, không dùng DB thật trong test — giữ tests <1s tổng cộng, repeatable, không pollute prod.
