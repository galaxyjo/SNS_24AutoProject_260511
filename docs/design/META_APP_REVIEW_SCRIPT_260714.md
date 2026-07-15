# Meta App Review — 화면 녹화 시연 대본 + 신청서 문구 (260714 작성)

대상 권한: `instagram_manage_messages`, `instagram_manage_comments`, `instagram_content_publish` (Standard → Advanced Access 승격)

> **260714 2차 수정:** 최초 작성 시 `instagram_content_publish`(FB→IG 자동 업로드, `launcher/main.py:254,263`의 `/media`+`/media_publish` 호출 — 오늘도 계속 정상 작동 중인 핵심 기능)가 누락돼 있었음. Claude(웹) 검토로 발견, 3번 섹션에 문구 추가. 지금 당장 기능이 막힌 건 `instagram_manage_messages`뿐(DM 답장 수신 문제, ERR-064)이라 급하지 않지만, 신청서가 앱의 사용 중인 권한을 한 번에 묶어 심사하는 방식이라 실제 사용 중인 이 3개는 전부 정직하게 답변하는 게 맞음. Marketing API / Live Video / Threads / WhatsApp Business 등은 이 프로젝트(`CLAUDE.md` 범위) 밖이라 이 신청에서 제외 권장 — 실제 사용 여부는 해당 담당자만 판단 가능.

---

## 1. 녹화 전 준비물

- 화면 녹화 프로그램: Windows는 `Win + Alt + R`(Xbox Game Bar, 기본 내장, 별도 설치 불필요) 또는 OBS Studio/Loom
- 등장 계정 2개: 비즈니스 계정(yuna18253) 화면 1개, 손님 역할 테스트 계정 화면 1개(이미 앱에 테스터로 등록된 "채솔" 계정 사용 권장 — 심사 목적상 테스터 계정으로 시연해도 무방)
- 녹화 해상도: 1080p 이상, 마우스 커서/클릭이 잘 보이게
- 길이: 2~4분 권장(너무 길면 심사관이 끝까지 안 볼 수 있음)
- 자막 또는 음성 설명: **영어 권장**(심사관 다수가 영어 기반, 한국어만 있으면 반려 사유가 될 수 있음) — 화면에 영어 자막을 넣거나, 편집 프로그램(무료: CapCut, Windows 사진 앱)으로 자막 삽입

---

## 2. 녹화 장면 순서 (스토리보드)

이미 오늘 Gate G에서 실제로 검증한 흐름 그대로 재현하면 됩니다.

**Scene 1 — 배경 설명 (5~10초, 첫 화면에 텍스트 오버레이 또는 내레이션)**
> "This is [Galaxy International Co., Ltd.]'s Instagram Business account. We help customers get pricing and consultation for our products through Instagram comments and DMs."

**Scene 2 — 손님이 댓글 남김 (10~15초)**
- 테스트 계정으로 비즈니스 계정의 게시물에 이동
- 댓글 작성: 예) "How much is this?" 또는 "가격 얼마예요?"
- 화면 캡션: "A customer asks about pricing in a public comment."

**Scene 3 — 비공개 답장(Private Reply) 도착 확인 (10~15초)**
- 테스트 계정의 Instagram DM함으로 전환
- 방금 도착한 비공개 메시지 보여주기(예: "답장 주시면 단가를 바로 안내드릴게요!")
- 화면 캡션: "Our system automatically sends a private reply to the commenter — this keeps pricing details out of the public comment section, protecting customer privacy."

**Scene 4 — 손님이 답장 (10~15초)**
- 테스트 계정에서 그 DM에 실제로 답장 입력·전송(예: "Yes, please tell me more")
- 화면 캡션: "The customer replies to continue the conversation privately."

**Scene 5 — 비즈니스 계정에서 대화 확인 + (가능하면) 후속 응답 (15~30초)**
- 비즈니스 계정 화면으로 전환, 해당 DM 스레드에서 손님의 답장이 도착해 있음을 보여줌
- 화면 캡션: "Our business receives the reply and continues assisting the customer with pricing and order details — all within Instagram Direct Messages, with the customer's explicit consent (they initiated contact via a comment)."

**Scene 6 — 마무리 (5~10초)**
> "This flow uses `instagram_manage_comments` to detect and respond to comments, and `instagram_manage_messages` to send and receive direct messages — enabling fast, private customer service entirely within Instagram, initiated only by the customer's own comment or message."

---

## 3. 신청서 제출용 영문 설명 문구 (그대로 복붙 가능)

### How will your app use `instagram_manage_comments`?

```
Our business (Galaxy International Co., Ltd.) sells products through Instagram.
Customers frequently leave comments on our posts asking about pricing or product
details. We use instagram_manage_comments to detect these comments in near
real-time and respond appropriately — either by flagging them for our team via
internal notifications, or by triggering a private reply (see
instagram_manage_messages usage below). We never comment on posts we do not own,
and we only respond to comments containing specific, pre-defined keywords
(e.g. price, cost, how much) to avoid unnecessary or spammy interactions.
```

### How will your app use `instagram_manage_messages`?

```
When a customer comments on one of our posts asking about pricing, our system
sends a one-time private reply (using the comment_id recipient type) inviting
them to continue the conversation privately, so pricing and order details are
not exposed publicly. If the customer replies, our team (assisted by an
automated response system) continues the conversation to answer product
questions, provide pricing, and assist with orders — entirely within Instagram
Direct Messages, and only with customers who first initiated contact through a
public comment or a direct message. We do not send unsolicited messages to
users who have not engaged with our content.
```

### How will your app use `instagram_content_publish`?

```
Our business curates product content and publishes it to our own Instagram
Business account on a regular schedule. We use instagram_content_publish to
create media containers and publish approved posts (images) to our own
account only — we never publish to accounts we do not own or manage. This is
a core part of our day-to-day content operations, running continuously with
automatic retry handling for transient failures.
```

---

## 4. 제출 위치

1. developers.facebook.com → 해당 앱(Galaxy International Co., Ltd.) 선택
2. 좌측 메뉴 **App Review → Permissions and Features**
3. `instagram_manage_messages`, `instagram_manage_comments`, `instagram_content_publish` 각각 옆의 **Request Advanced Access** (그 외 Marketing API/Live Video/Threads/WhatsApp Business 등은 이번 제출에서 제외 — 이 프로젝트와 무관, 실제 사용 여부는 별도 담당자 확인 필요)
4. 녹화한 영상 업로드(또는 YouTube 미등록 링크 첨부) + 위 영문 설명 문구 붙여넣기
5. 제출 → Meta 검토(통상 며칠~몇 주 소요)

---

## 5. 참고

- 이 시연은 오늘(260714) Gate G에서 실제로 검증한 흐름(comment_poller → comment_auto_reply Private Reply)을 그대로 재현한 것 — 코드는 이미 존재하고 커밋(`4f3f38e`)까지 완료된 상태.
- 승인 전까지는 테스터 등록된 계정끼리만 완전한 기능이 보장되므로(ERR-064/FP-048/INC-036 참조), 실제 신규 손님 대상 자동 응답은 승인 후에 안전하게 켜는 것을 권장.
