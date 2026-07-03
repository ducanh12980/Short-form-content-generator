# Content Learning System — Quy trình tạo video ngắn tối ưu

> Mục tiêu cuối cùng không phải là tạo ra một video, mà là làm cho video thứ 100 tốt hơn video thứ 10.

## Kiến trúc tổng thể: 3 hệ thống con

```
PRODUCTION            OPTIMIZATION            KNOWLEDGE
(tạo ra video)    →    (video sau tốt hơn)  →  (tích lũy tri thức)

Brand Identity          Hypothesis               Knowledge Base
    ↓                       ↓                         ↓
Backlog → Idea           Collect Data              Decision Log
    ↓                       ↓
Hook, Research            Cohort
    ↓
Script, Storyboard
    ↓
Voice, Visual
    ↓
Edit, Publish
```

Một bên tạo video, một bên làm cho video sau tốt hơn — tách rõ để không lẫn "hôm nay quay gì" với "tại sao video hôm qua chạy tốt".

---

## Bước 0: Xác định Brand Identity (làm 1 lần, trước khi vào Production)

Thiếu bước này, sau vài chục video kênh rất dễ bị "lệch chất" — mỗi video một phong cách, khán giả không nhận diện được kênh.

|Yếu tố|Lựa chọn ví dụ|
|-|-|
|Giọng điệu|Chuyên gia / Bạn bè / Hài hước / Bí ẩn|
|Phong cách hình ảnh|Dark / Minimal / Documentary / Cinematic|
|Màu sắc \& Font|Cố định bảng màu, font chữ xuyên suốt kênh|
|Kiểu CTA|Trực tiếp / Gợi mở / Hài hước|

```
Kênh A: Chuyên gia → Hook nghiêm túc → Visual tối giản
Kênh B: Hài hước   → Hook troll       → Visual kiểu meme
```

Mọi bước từ Hook đến Visual bên dưới đều cần nhất quán với Brand Identity đã chọn.

## Content Backlog (chạy song song, nuôi Production liên tục)

```
Idea Pool → Research → Ready → Recording → Published
  100    →    20     →   10   →     5     →     3
```

Idea Pool luôn nạp thêm từ trend, bình luận, đối thủ... rồi lọc dần qua từng giai đoạn. Bước 1-2 dưới đây lấy input từ backlog này thay vì phải nghĩ ý tưởng mới mỗi ngày.

---

## Giai đoạn 1: Chiến lược

**1. Xác định chủ đề \& đối tượng**

* Đối tượng xem, mục tiêu video, nỗi đau (pain point), giá trị mang lại
* Nguồn ý tưởng: xu hướng TikTok/Shorts, bình luận người xem, câu hỏi thường gặp, Reddit/Quora, tin tức, nội dung đối thủ

**2. Brainstorm nhiều Hook**

* Với 1 ý tưởng, viết 5 phiên bản hook khác nhau (Hook A-E), chỉ chọn 1 mạnh nhất
* 3 giây đầu quyết định phần lớn khả năng giữ chân người xem
* Ví dụ: "5 sai lầm khi uống nước" → "90% mọi người đang uống nước sai cách"

## Giai đoạn 2: Nội dung

**3. Research**

* Video kiến thức: kiểm tra nguồn, chọn số liệu, tìm ví dụ
* Video bán hàng: USP, pain point, lợi ích
* Video review: ưu điểm, nhược điểm, đối tượng phù hợp
* LLM hỗ trợ research nhưng cần kiểm tra lại thông tin quan trọng

**4. Viết Script** — cấu trúc Hook → Body → CTA

* Hook (0-3s): câu hỏi gây tò mò / số liệu sốc / mâu thuẫn nhận thức
* Body (2-3 ý chính): mỗi ý 5-8s, nói tự nhiên như kể chuyện
* CTA: 1 lời kêu gọi hành động rõ ràng

**5. Storyboard**

|Thời gian|Nội dung|
|-|-|
|0-3s|Hook|
|3-8s|Ý 1|
|8-15s|Ý 2|
|15-23s|Ý 3|
|23-30s|CTA|

## Giai đoạn 3: Tài nguyên

**6. Voice** — phù hợp giới tính, độ tuổi, tốc độ nói, cảm xúc của đối tượng

**7. Visual** — thứ tự ưu tiên chi phí/hiệu quả:

1. Ảnh + hiệu ứng chuyển động nhẹ (Ken Burns) — rẻ nhất, đủ dùng cho hầu hết video kiến thức
2. Video stock / tự quay — khi cần chuyển động thật
3. AI Video (Sora, Veo, Kling) — chỉ dùng khi không thể thay thế, vì chi phí cao nhất

## Giai đoạn 4: Hậu kỳ

**8. Edit** — ghép voice + visual + subtitle + animation, thêm intro/outro, transition, logo/watermark

**9. Music \& Subtitle**

* Phụ đề động bắt buộc (85% người xem tắt tiếng, đọc phụ đề trước khi bật tiếng)
* Nhạc nền chỉ hỗ trợ, không lấn át giọng đọc, chỉ thêm sau khi video đã hoàn chỉnh

**10. QA** — kiểm tra lỗi chính tả, subtitle, âm lượng, pacing, cảnh có khớp lời thoại, hook có đủ mạnh, CTA có rõ ràng

## Giai đoạn 5: Phân phối

**11. Publish** — tối ưu riêng theo nền tảng

|Nền tảng|Lưu ý|
|-|-|
|TikTok|Tối ưu 21-34s, thuật toán ưu tiên completion rate|
|Reels|Caption dài hơn thường hiệu quả hơn|
|Shorts|Tối đa 60s, nhưng 40-50s thường có watch time tổng cao hơn|

Chuẩn bị: tiêu đề, caption, hashtag, thumbnail — điều chỉnh riêng cho từng nền tảng, không copy y hệt.

## Giai đoạn 6: Học hỏi liên tục (quan trọng nhất)

**12. Đặt giả thuyết (Hypothesis) — không tối ưu từng video, tối ưu tri thức**

Thay vì "video này retention thấp", đặt giả thuyết cụ thể và kiểm chứng qua nhiều video:

* H1: Hook gây sốc > Hook đặt câu hỏi
* H2: Video 25s > Video 45s
* H3: Giọng nam > Giọng nữ

**Lưu ý về độ tin cậy:** số video cần thiết để kết luận phụ thuộc vào cỡ chênh lệch. Chênh lệch lớn (70% vs 50%) → 10-15 video đủ. Chênh lệch nhỏ (68% vs 63%) → cần nhiều hơn, và phải kiểm tra 2 dải số liệu có tách biệt rõ hay chồng lấn nhau trước khi kết luận.

**13. Phân tích theo Cohort — không phân tích từng video đơn lẻ**

Gom nhóm 15-20 video theo tiêu chí (chủ đề, có người thật hay AI, hook style...) rồi so sánh retention/completion trung bình giữa các nhóm.

* Ví dụ: niche AI (68%) vs niche sức khỏe (52%) → vấn đề là niche, không phải hook
* **Lưu ý quan trọng:** các nhóm so sánh nên đăng xen kẽ trong cùng khung thời gian, không tách theo giai đoạn liên tiếp — tránh nhầm lẫn giữa "khác biệt do nội dung" và "khác biệt do thuật toán/mùa vụ thay đổi theo thời gian"

**14. Xây Knowledge Base (không chỉ Asset Library)**

Tài sản quý nhất không phải ảnh/nhạc/CTA, mà là insight đã kiểm chứng:

* "Audience 18-24: hook dạng 'Bạn đang làm sai...' tốt hơn 'Bạn có biết...'"
* "Video >45s: completion giảm mạnh"
* "Mở đầu bằng mặt người: CTR cao hơn"

Vẫn nên giữ Asset Library (hook/CTA/nhạc/hiệu ứng/prompt hiệu quả) làm khung tham khảo, nhưng tránh copy-paste nguyên mẫu nhiều lần — dễ gây audience fatigue và giảm reach do nội dung quá lặp lại.

**15. Decision Log**

|Ngày|Quyết định|Lý do|Kết quả|Độ tin cậy|
|-|-|-|-|-|
|2/7|Giảm 60s→35s|Completion thấp|+18% completion|Cao (n=15, chênh lệch rõ)|
|6/7|Nam→nữ|Test H3|Không khác biệt|Cao (kết luận: không quan trọng)|
|10/7|Hook thống kê|Test H1|+9% retention|Trung bình (n=8, cần thêm data)|

Cột "Độ tin cậy" giúp phân biệt insight đã chốt (có thể tin tưởng áp dụng) với quan sát ban đầu (cần test thêm trước khi dựa vào để ra quyết định lớn).

---

## KPI cho từng bước — hệ thống chẩn đoán

Gắn KPI riêng cho từng bước giúp khi có vấn đề, biết ngay cần sửa ở đâu thay vì đoán cảm tính.

|Bước|KPI theo dõi|
|-|-|
|Hook|Retention 3 giây đầu|
|Body|Retention 30-70% thời lượng|
|CTA|Follow rate|
|Thumbnail|CTR (click-through rate)|
|Caption|Comment rate|

Cách chẩn đoán dựa trên KPI:

```
Retention 3s thấp        →  Vấn đề ở Hook
Retention 3s tốt nhưng
Completion thấp          →  Vấn đề ở Body
Completion cao nhưng
Follow thấp               →  Vấn đề ở CTA
```

## Vòng lặp tổng thể

```
0. Brand Identity (làm 1 lần)
        ↓
1. Chủ đề \& đối tượng (lấy từ Backlog)
        ↓
2. Brainstorm Hook
        ↓
3. Research
        ↓
4. Script
        ↓
5. Storyboard
        ↓
6. Voice
        ↓
7. Visual
        ↓
8. Edit
        ↓
9. Music \& Subtitle
        ↓
10. QA
        ↓
11. Publish (tối ưu theo nền tảng)
        ↓
12. Đặt \& test giả thuyết
        ↓
13. Phân tích theo Cohort
        ↓
14. Cập nhật Knowledge Base
        ↓
15. Ghi Decision Log
        ↺ Quay lại bước 1
```

**Nguyên tắc cốt lõi:** AI chỉ là công cụ tăng tốc sản xuất (giai đoạn 1-11). Lợi thế cạnh tranh lâu dài nằm ở hệ thống học hỏi (giai đoạn 6) — cách đặt giả thuyết, thu thập dữ liệu theo cohort, và ra quyết định dựa trên bằng chứng có kiểm soát độ tin cậy. Đây là phần khó sao chép nhất.
