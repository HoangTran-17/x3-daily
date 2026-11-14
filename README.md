# x3-daily

Soạn bản tin mỗi sáng cho máy đọc sách Xteink X3 bằng GitHub Actions + GitHub Pages.

## TL;DR

- `brief.json` (schema v1, ≤4 KB): firmware vẽ lên màn ngủ. Có thời tiết, giá vàng nhẫn 9999, tin AI, châm ngôn.
- `bao-sang-YYYYMMDD.epub` + `opds.xml`: bản "Báo sáng" để đọc trên máy qua OPDS (giữ 7 số gần nhất).
- Lịch Google **không** nằm trên Pages hay trong artifact nào. Bản có lịch chỉ được ghi vào 1 secret gist.
- Pages URL dự kiến: `https://hoangtran-17.github.io/x3-daily/`
- Chạy lúc ~04:10 giờ VN mỗi ngày. Một nguồn lỗi thì bỏ field đó, bản tin vẫn ra.

## Cấu trúc

| Module | Việc |
|---|---|
| `x3daily/gold.py` | Giá nhẫn 9999 (PNJ), lịch sử `data/gold.csv`, % biến động |
| `x3daily/weather.py` | Open-Meteo: TP.HCM + Hà Tĩnh |
| `x3daily/news.py` | RSS/Atom (`xml.etree`), lọc 24 giờ, khử trùng lặp |
| `x3daily/quotes.py` | Châm ngôn từ `quotes.txt`, chọn theo ngày |
| `x3daily/calendar_ics.py` | Parse ICS Google Calendar (bí mật) |
| `x3daily/brief.py` | Ghép `brief.json`, ép ≤4 KB, bản công khai không có `events` |
| `x3daily/epub.py`, `opds.py` | Báo sáng EPUB + feed OPDS tĩnh |
| `x3daily/build.py` | Điều phối (`python -m x3daily build`) |
| `x3daily/translate.py` | Dịch tin AI sang tiếng Việt bằng Gemini API (tuỳ chọn, `python -m x3daily translate-news`) |
| `prompts/news_translate.md` | Prompt cho bước Gemini |

## Chạy thử ở máy local

```
python -m x3daily collect-news   # ghi work/news.json (tuỳ chọn, build tự lấy nếu thiếu)
python -m x3daily translate-news # cần env GOOGLE_API_KEY; ghi work/news_vi.json
python -m x3daily build          # ghi _site/ và cập nhật data/gold.csv
python -m x3daily backfill-gold  # thêm ngày còn thiếu vào data/gold.csv từ API lịch sử PNJ
python -m pytest -q              # test offline
```

- Cần Python 3.11+. Chạy `build` chỉ cần stdlib. Muốn có EPUB: `pip install` x3book (xem dưới).
- Thiếu `x3book` thì bản tin vẫn ra, chỉ bỏ số EPUB hôm đó.
- `_site/` và `out-private/` (bản có lịch, chỉ có khi đặt `GCAL_ICS_URL`) nằm trong `.gitignore`. `data/gold.csv` được commit.

## Cài đặt trên GitHub

1. Tạo repo public `HoangTran-17/x3-daily`, push code này lên (chưa làm).
2. **Settings → Pages → Source: GitHub Actions**.
3. Tạo repo public `HoangTran-17/x3book` (chưa tồn tại). Workflow cài tool bằng
   `pip install git+https://github.com/HoangTran-17/x3book`. Chưa có repo này thì bước build **sẽ lỗi**.
4. Thêm secret (Settings → Secrets and variables → Actions). Tất cả đều **tuỳ chọn**:

| Secret | Dùng để | Thiếu thì |
|---|---|---|
| `GOOGLE_API_KEY` | Gemini dịch/tóm tắt tin AI sang tiếng Việt | Tin giữ tiếng Anh, EPUB ghi "(chưa dịch)" |
| `GCAL_ICS_URL` | Link ICS bí mật của Google Calendar | Không có ô lịch |
| `GIST_TOKEN` | PAT chỉ có quyền gist, để ghi bản có lịch | Không có ô lịch |
| `GIST_ID` | ID của secret gist chứa bản có lịch | Không có ô lịch |

5. Chạy tay lần đầu: **Actions → Bản tin hằng ngày → Run workflow**.

### Tạo `GOOGLE_API_KEY` (Gemini API, free tier)

- Tạo key ở Google AI Studio bằng account Google cá nhân. Free tier không cần bật billing.
- Model mặc định `gemini-3.5-flash-lite` (đổi bằng repo variable `GEMINI_MODEL`: Settings → Secrets and variables → Actions → Variables). Mỗi ngày 1 request cho cả 5 tin.
- Free tier: Google có thể dùng nội dung gửi lên để cải thiện sản phẩm. Nội dung gửi đi chỉ là tin RSS công khai.
- Key chỉ gửi trong header `x-goog-api-key`. Log chỉ in mã HTTP khi lỗi (429 = hết quota, 400/403 = key sai).
- Bước lỗi thì exit 1, workflow vẫn tiếp tục (`continue-on-error`).
- Tin không dịch được: EPUB ghi "(chưa dịch)" cạnh tiêu đề. `brief.json` vẫn dùng tiêu đề gốc.

### Lịch Google (bí mật)

Repo public nên ai có tài khoản GitHub cũng tải được artifact `github-pages`. Vì vậy bản có lịch
không vào Pages. Build ghi nó ra `out-private/brief.json` (ngoài `_site/`), rồi Actions đẩy lên 1 secret gist.

1. Google Calendar → Settings → lịch của bạn → **Secret address in iCal format**. Copy link vào secret `GCAL_ICS_URL`.
2. Tạo secret gist: vào <https://gist.github.com>, tên file `brief.json`, nội dung `{}`
   (GitHub không cho tạo gist rỗng), bấm **Create secret gist**.
   `GIST_ID` là đoạn hex cuối URL gist: `https://gist.github.com/<user>/<GIST_ID>`.
3. Tạo token chỉ ghi được gist, chọn 1 trong 2:
   - Classic PAT: Settings → Developer settings → Personal access tokens → Tokens (classic). Chỉ tick scope `gist`.
   - Fine-grained PAT: Account permissions → **Gists: Read and write**. Không cần quyền repo nào.
4. Thêm 3 secret vào repo: `GCAL_ICS_URL`, `GIST_TOKEN` (token ở bước 3), `GIST_ID` (chỉ ID, không phải URL).
   Thiếu 1 trong 3 thì bước gist tự bỏ qua, workflow vẫn xanh. Ghi gist lỗi thì có warning, Pages vẫn deploy.
5. Link máy cần tải (không gắn commit SHA nên luôn là bản mới nhất):
   `https://gist.githubusercontent.com/<user>/<GIST_ID>/raw/brief.json`
6. Ghi link đó (1 dòng) vào file `/.crosspoint/brief_url.txt` trên thẻ SD của máy. Không có file này thì firmware
   dùng bản công khai trên Pages (không có lịch).
7. **Cảnh báo:** secret gist chỉ là không được liệt kê, không có mật khẩu. Ai có link gist thì đọc được lịch hôm đó.
   Lộ link thì xoá gist, tạo gist mới và đổi `GIST_ID` + `brief_url.txt`.
8. Raw gist có thể bị cache ~5 phút sau khi cập nhật. Actions chạy lúc ~04:10, máy tải lúc sáng sau đó nên không ảnh hưởng.
9. Bảo vệ dữ liệu lịch:
   - Không commit dữ liệu lịch. `out-private/` không nằm trong artifact Pages, cũng không được upload artifact nào khác.
   - Log không in sự kiện, không in URL, không in token.
   - EPUB và `/brief.json` công khai không có lịch (có test kiểm tra).
10. Giới hạn parser ICS (stdlib, tự viết):
   - **Không** mở rộng `RRULE` (sự kiện lặp). Sự kiện lặp chỉ hiện đúng ngày `DTSTART` gốc. Ngày lặp sau đó sẽ không hiện.
   - Bỏ qua `EXDATE`, `RECURRENCE-ID`. Bỏ sự kiện `STATUS:CANCELLED`.
   - Sự kiện cả ngày: ô `time` là `"Cả ngày"` (không phải `HH:MM`). Cần kiểm tra firmware vẽ được chuỗi này.
   - Múi giờ `TZID` khác VN cần database múi giờ của hệ điều hành. Không có thì coi như giờ VN.
   - Tối đa 6 sự kiện, tiêu đề ≤60 ký tự.

## Nguồn dữ liệu

### Giá vàng nhẫn 9999: PNJ

- Nguồn: `https://edge-api.pnj.io/ecom-frontend/v1/get-gold-price?zone=00`, dòng `N24K` ("Nhẫn Trơn PNJ 999.9", TP.HCM).
- Đã thử GET thật 03/11/2026. Trả JSON sạch, không cần key.
- Lý do chọn:
  - SJC chặn bot (HTTP 403, trang Cloudflare "Just a moment").
  - webgia.com che số bằng chuỗi mã hoá ở nhiều dòng; chỉ vài dòng hiện số rõ.
  - Hai nguồn còn lại không tiện: API BTMC cần key, Phú Quý chặn kết nối.
- Đơn vị gốc: nghìn đồng/chỉ. Đổi sang triệu đồng/lượng: `13490 → "134,9"`.
- Rủi ro: API này không có tài liệu chính thức. Nó có thể đổi. Khi lỗi, bản tin bỏ ô vàng.
- Lịch sử: Actions ghi 1 dòng mỗi ngày vào `data/gold.csv` (`date,buy,sell`, nghìn đồng/chỉ). % tính theo giá **bán ra**.
  - `brief.json`: 1 tháng = 30 ngày trước, 3 tháng = 91 ngày, 1 năm = 365 ngày (field `d1m`/`d3m`/`d1y`).
  - EPUB: hôm nay + 1 tuần (7 ngày), 1 tháng, 3 tháng, 6 tháng (182 ngày), 12 tháng. Mỗi mốc ghi ngày, giá mua/bán, chênh lệch giá bán (tr/lượng và %).
  - Lấy bản ghi mới nhất ≤ ngày mục tiêu, cũ hơn tối đa 7 ngày (mốc 1 tuần: tối đa 2 ngày, để không lấy giá 14 ngày trước làm "1 tuần").
  - Không có bản ghi: `brief.json` bỏ field đó; EPUB ghi "chưa có".
- Nguồn của từng dòng `data/gold.csv`:
  - Từ 2026-11-03: Actions ghi giá N24K lúc chạy (~04:10, có hôm chạy trễ). Lúc 04:10 PNJ thường chưa cập nhật, nên giá là giá cuối của ngày hôm trước.
  - Trước 2026-11-03 (2025-11-06 → 2026-11-02, nạp ngược 13/11/2026): `https://edge-api.pnj.io/ecom-frontend/v1/get-gold-price-history?zone=00&date=YYYYMMDD`, sản phẩm "Nhẫn Trơn PNJ 999.9" (cùng tên `tensp` của N24K), lấy bản ghi cuối trong ngày.
  - Endpoint lịch sử không có tài liệu. Đơn vị: nghìn đồng/lượng, chuỗi `"137.400"` (dấu chấm ngăn nghìn) → chia 10 thành nghìn đồng/chỉ.
  - Ngày không có dữ liệu (chủ nhật, Tết, lễ) không có dòng.
- Nạp ngược lại / lấp ngày thiếu: `python -m x3daily backfill-gold --days 372`. Lệnh chỉ thêm ngày còn thiếu, không ghi đè dòng có sẵn.

### Thời tiết

Open-Meteo (không key). `now` = mô tả tiếng Việt từ `weather_code`, `range` = `min–max°` (làm tròn).

### Tin AI

Nguồn (sửa trong `x3daily/config.py`): Google AI blog, MIT Technology Review (AI), TechCrunch (AI), The Verge (AI).
Lấy tối đa 5 tin trong 24 giờ, bỏ trùng link và tiêu đề gần giống.
Tin quảng cáo của nguồn (ví dụ vé sự kiện TechCrunch) chưa được lọc.

### Châm ngôn

`quotes.txt`: mỗi dòng `câu | tác giả`. 60 câu. Chọn theo `ngày.toordinal() % số câu`: cùng ngày cùng câu.
Câu danh nhân do tự diễn đạt lại tiếng Việt, nguồn gốc câu nói mang tính phổ biến, chưa đối chiếu từng văn bản gốc.

## Báo sáng EPUB + OPDS

- EPUB có 4 file (mỗi file 1 mục TOC): thời tiết, giá vàng, tin AI, châm ngôn.
- Giá vàng 30 ngày viết thành từng dòng, **không dùng `<table>`**: CrossVi làm phẳng bảng và in nhãn "Tab Row N, Cell M" trước mỗi ô.
- Sau khi tạo, workflow chạy `x3book tune` rồi `x3book check`. Check lỗi thì bỏ số hôm đó.
- Pages deploy bằng artifact nên mỗi lần deploy thay cả site. Build tải lại EPUB cũ từ `opds.xml` đang chạy trên Pages (chỉ nhận tên `bao-sang-YYYYMMDD.epub`, host luôn lấy từ `PAGES_BASE_URL`). Lỗi tải thì bỏ qua số đó.
- `opds.xml`: OPDS 1.2 acquisition feed tĩnh, 7 số gần nhất, link tuyệt đối.

### Thêm feed vào máy X3

1. Mở OPDS browser trên máy (CrossVi).
2. Thêm server mới, URL: `https://hoangtran-17.github.io/x3-daily/opds.xml`.
3. Mở feed, chọn "Báo sáng dd/mm/yyyy", tải về.

Máy X3 không bắt tay TLS được với github.io, nên workflow còn đẩy `_site` lên branch `device` và máy đọc qua contents API (firmware tự gửi `Accept: application/vnd.github.raw`):

- Feed: `https://api.github.com/repos/HoangTran-17/x3-daily/contents/opds-api.xml?ref=device`
- Brief: `https://api.github.com/repos/HoangTran-17/x3-daily/contents/brief.json?ref=device`
- Base đổi được bằng env `DEVICE_BASE_URL`.

(Tên menu trên firmware có thể khác. Chưa thử trên máy thật.)

## Lịch chạy

- Cron `10 21 * * *` UTC = 04:10 giờ VN. GitHub có thể trễ vài phút đến vài chục phút giờ cao điểm.
- Workflow 3 job: `news` (đọc RSS, Gemini tuỳ chọn) → `build` (ghi site, commit `gold.csv`) → `deploy` (Pages).
- Workflow `tests.yml` chạy pytest khi push/PR. Test `x3book check` tự bỏ qua nếu chưa cài x3book.

## License

MIT, xem `LICENSE`.
