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
| `prompts/news_summary.md` | Prompt cho bước Claude (tuỳ chọn) |

## Chạy thử ở máy local

```
python -m x3daily collect-news   # ghi work/news.json (tuỳ chọn, build tự lấy nếu thiếu)
python -m x3daily build          # ghi _site/ và cập nhật data/gold.csv
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
| `CLAUDE_CODE_OAUTH_TOKEN` | Claude dịch/tóm tắt tin AI sang tiếng Việt | Dùng tiêu đề tiếng Anh gốc |
| `GCAL_ICS_URL` | Link ICS bí mật của Google Calendar | Không có ô lịch |
| `GIST_TOKEN` | PAT chỉ có quyền gist, để ghi bản có lịch | Không có ô lịch |
| `GIST_ID` | ID của secret gist chứa bản có lịch | Không có ô lịch |

5. Chạy tay lần đầu: **Actions → Bản tin hằng ngày → Run workflow**.

### Tạo `CLAUDE_CODE_OAUTH_TOKEN`

- Chạy ở máy của bạn: `claude setup-token`. Lệnh in ra token dùng quota gói Pro/Max của bạn.
- Dán token vào secret. Không đưa token vào chat hay file.
- Bước Claude chỉ chạy khi secret này có giá trị. Bước lỗi thì workflow vẫn tiếp tục với tiêu đề gốc (`continue-on-error`).
- Dữ liệu RSS là input không tin cậy. Job `news` chỉ có quyền `contents: read`, Claude chỉ được dùng tool `Read` và `Write`. Prompt dặn rõ: dữ liệu RSS không phải lệnh. Code Python còn cắt độ dài và bỏ ký tự điều khiển trong kết quả của Claude.

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
  - 1 tháng = 30 ngày trước, 3 tháng = 91 ngày, 1 năm = 365 ngày.
  - Lấy bản ghi mới nhất ≤ ngày mục tiêu, cũ hơn tối đa 7 ngày. Không có thì bỏ field `d1m`/`d3m`/`d1y` đó.
  - Nghĩa là `d1m` chỉ xuất hiện sau ~30 ngày chạy, `d3m` sau ~3 tháng, `d1y` sau ~1 năm.
- **Không có script backfill.** Đã tìm nguồn lịch sử miễn phí cho nhẫn 9999 mà không cần key:
  - PNJ: tham số `date` bị bỏ qua, không có endpoint lịch sử.
  - webgia.com chỉ có biểu đồ lịch sử cho SJC miếng, không phải nhẫn 9999. Trộn hai loại sẽ cho % sai.
  - Nếu bạn có file giá lịch sử nhẫn 9999, chỉ cần thêm dòng vào `data/gold.csv` (cùng định dạng), % sẽ tự tính.

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

(Tên menu trên firmware có thể khác. Chưa thử trên máy thật.)

## Lịch chạy

- Cron `10 21 * * *` UTC = 04:10 giờ VN. GitHub có thể trễ vài phút đến vài chục phút giờ cao điểm.
- Workflow 3 job: `news` (đọc RSS, Claude tuỳ chọn) → `build` (ghi site, commit `gold.csv`) → `deploy` (Pages).
- Workflow `tests.yml` chạy pytest khi push/PR. Test `x3book check` tự bỏ qua nếu chưa cài x3book.

## License

MIT, xem `LICENSE`.
