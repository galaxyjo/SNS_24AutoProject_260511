# Instagram 계정 온보딩 · 무제한 토큰 발급 매뉴얼

**최종 개정**: 2026-09-25 (260925 aijomoojin 전환 실작업 기준 전면 교체)
**적용 대상**: 신규 Instagram 계정을 이 시스템의 게시 자동화에 편입할 때마다 매번
**핵심 변경**: 기존 `instagram_login`(IGAA · **60일 만료**) 방식을 **폐기**하고, `facebook_login`(**만료 없는 페이지 토큰**)을 표준으로 확정한다.

> **왜 바꿨나** — 260925 19:35 KST에 aijomoojin(IDN-000036)의 IGAA 토큰이 만료돼 20:00 슬롯 게시가 실패했다(`code 190 Session has expired`). 같은 시스템의 YUNA(IDN-000041)는 `facebook_login`이라 한 번도 만료된 적이 없다. 계정을 수십 개로 확장하면 60일마다 전 계정 수동 갱신은 불가능하므로, **신규 계정은 예외 없이 이 문서의 방식으로만 온보딩한다.**

---

## 0. 시작 전 준비물 (계정 1개당)

| 항목 | 비고 |
|---|---|
| Instagram 계정 로그인 정보 | **프로페셔널(비즈니스/크리에이터)** 이어야 함. 개인 계정이면 API 게시 불가 |
| Facebook 페이지 | 그 IG 계정 전용으로 1개. 없으면 새로 생성 |
| Meta 개발자 앱 | 기존 앱 재사용 가능(계정마다 새로 만들 필요 없음) |
| 앱 ID / 앱 시크릿 | `developers.facebook.com` → 앱 → 설정 → 기본 설정 |

**소요 시간**: 계정당 약 10~15분 (처음엔 20분).

---

## 1단계. Instagram 계정을 프로페셔널로 전환

1. Instagram 앱 → 설정 → 계정 종류 및 도구 → **프로페셔널 계정으로 전환**
2. **비즈니스** 또는 **크리에이터** 선택

> 개인 계정이면 이후 모든 단계가 실패한다. **가장 먼저 확인할 것.**

---

## 2단계. Facebook 페이지 ↔ Instagram 연결 ★가장 많이 틀리는 곳

**계정 센터(accountscenter.facebook.com) 연결은 이것이 아니다.** 계정 센터에 IG가 보여도 API는 인식하지 못한다.

올바른 경로 — 둘 중 하나:
- **Facebook 페이지 → 설정 → 연결된 계정 → Instagram → [연결]** → 대상 IG 계정 로그인
- 또는 **Meta Business Suite → 설정 → 비즈니스 자산 → Instagram 계정 → 추가**

**검증 방법**: 3단계 이후 API로 `instagram_business_account`가 나오면 성공. 비어 있으면 연결이 안 된 것이다.

| 구분 | 계정 센터 연결 | 페이지↔IG 연결(필요) |
|---|---|---|
| 목적 | 로그인·광고 공유 | 페이지가 IG를 **자산으로 소유** |
| API 인식 | ❌ 안 됨 | ✅ 됨 |

---

## 3단계. 실제 Page ID 확인 ★주소창 숫자와 다를 수 있음

페이지 주소가 `facebook.com/profile.php?id=61562343393619` 형태여도 **그 숫자는 API용 Page ID가 아니다.**

Graph API Explorer(`developers.facebook.com/tools/explorer`)에서 확인:

```
me/accounts?fields=id,name
```

여기 나오는 `id`가 **진짜 Page ID**다. (260925 실사례: 표시용 `61562343393619` → 실제 `345212562017606`)

---

## 4단계. Explorer 초기 설정

Graph API Explorer 우측 패널에서:

1. **Meta 앱**: 사용할 앱 선택
2. **도메인 드롭다운**: 반드시 **`graph.facebook.com`** — `graph.instagram.com`이면 이 매뉴얼의 방식이 아니다(구 IGAA 경로로 빠짐)
3. **사용자 또는 페이지**: **사용자 토큰**
4. **Permissions** 탭에서 아래 7개 체크:

```
pages_show_list
pages_read_engagement
pages_manage_posts
business_management
instagram_basic
instagram_content_publish
instagram_manage_comments
instagram_manage_messages
```

> DM·댓글 자동응답을 쓰지 않는 계정이면 뒤 2개는 생략 가능. 나머지는 필수.

5. **`Generate Access Token`** 클릭 → 로그인·승인

---

## 5단계. 단기 → 장기 사용자 토큰 (★이 단계를 건너뛰면 무제한이 안 된다)

4단계에서 받은 토큰은 **1~2시간짜리 단기 토큰**이다. 여기서 뽑은 페이지 토큰도 똑같이 단기가 된다.

**앱 시크릿 입력 없이** 연장하는 방법(권장):

1. 4단계 토큰을 **토큰 칸 오른쪽 복사 아이콘**으로 복사 (드래그 복사 ❌ — 뒷부분이 잘린다)
2. 새 탭에서 접속:
   ```
   https://developers.facebook.com/tools/debug/accesstoken/
   ```
3. 붙여넣기 → **`디버그`** 클릭
4. 결과 화면 **맨 아래** → **`액세스 토큰 연장`**(Extend Access Token) 클릭
5. 새로 나타난 **긴 토큰을 복사** ← 60일짜리 **장기 사용자 토큰**

**대안(앱 시크릿 사용)**: Explorer 경로칸에 입력 후 제출

```
oauth/access_token?grant_type=fb_exchange_token&client_id={앱ID}&client_secret={앱시크릿}&fb_exchange_token={단기토큰}
```

> **오해 주의**: 여기서 나오는 60일 토큰은 **중간 재료이며 저장하지 않는다.** 최종 저장물은 6단계의 페이지 토큰이고, 그것은 **만료가 없다.**

---

## 6단계. 무제한 페이지 토큰 발급

1. Explorer로 복귀
2. **액세스 토큰 입력칸의 내용을 전부 지우고**, 5단계의 **장기 사용자 토큰을 직접 붙여넣기**
   > ⚠️ 드롭다운에서 페이지를 선택하는 방식은 안 된다 — 5단계를 거치지 않은 단기 토큰이 쓰여 만료가 남는다.
3. 경로칸에 입력 후 **제출**:
   ```
   {PageID}?fields=access_token
   ```
4. 응답의 **`access_token` 값만** 복사 ← **이것이 무제한 페이지 토큰**

**복사 시 3대 실수 (260925 실제 전부 발생)**

| 실수 | 증상 | 방지 |
|---|---|---|
| 드래그 복사로 뒷부분 잘림 | `Malformed access token` | 복사 아이콘 사용 |
| JSON 찌꺼기 포함 (`...","is_valid":true`) | `Malformed access token` | **따옴표 안쪽 값만** 복사 |
| 붙여넣기 누락 | 길이 0 | 저장 후 반드시 7단계 검증 |

> 페이지 토큰은 보통 알파벳 대문자로 끝난다. 값 안에 `"` `,` `:` `true` `access_token` 같은 글자가 **하나도 없어야** 한다.

---

## 7단계. 프로젝트에 등록

### 7-1. `.env` (비밀값)

`credential_key`가 `XXX`인 계정은 아래 2줄을 사용한다. **따옴표·앞뒤 공백·줄바꿈 없이 한 줄**로 붙여넣는다.

```
XXX_INSTA_IG_USER_ID=17841xxxxxxxxxxxx
XXX_INSTA_ACCESS_TOKEN=EAAxxxxxxxxxxxxxxxxxxxx
```

(예: aijomoojin은 `credential_key=AI` → `AI_INSTA_IG_USER_ID` / `AI_INSTA_ACCESS_TOKEN`)

### 7-2. Airtable `Account_Registry`

| 필드 | 값 |
|---|---|
| `account_code` | `IDN-0000NN` (신규 채번) |
| `api_provider` | **`facebook_login`** ← 이 문서 방식은 반드시 이것 |
| `ig_user_id` | 6단계에서 확인한 `instagram_business_account.id` |
| `credential_key` | `.env` 변수 접두어 (예: `AI`) |
| `automation_enabled` | 준비 완료 후 `true` |

> `ig_user_id`는 Airtable과 `.env` **양쪽이 같아야** 한다. 다르면 코드가 게시를 Fail-closed로 차단한다.

---

## 8단계. 검증 (등록 직후 반드시)

아래를 실행해 **6개 항목이 전부 통과**해야 온보딩 완료다.

```bash
cd C:\SNS_24AutoProject_260511 && PYTHONUTF8=1 .venv/Scripts/python.exe -c "
import os,requests,datetime
from dotenv import load_dotenv
load_dotenv(r'C:\SNS_24AutoProject_260511\.env', override=True)
KEY='AI'; PAGE='345212562017606'
t=os.getenv(KEY+'_INSTA_ACCESS_TOKEN','').strip(); u=os.getenv(KEY+'_INSTA_IG_USER_ID','').strip()
d=requests.get('https://graph.facebook.com/v21.0/debug_token',params={'input_token':t,'access_token':t},timeout=20).json().get('data',{})
e=d.get('expires_at')
print('1 type      :',d.get('type'),'(PAGE 여야 함)')
print('2 valid     :',d.get('is_valid'))
print('3 만료      :','없음(무제한)' if e in (0,None) else datetime.datetime.fromtimestamp(e))
print('4 publish권한:','instagram_content_publish' in d.get('scopes',[]))
r=requests.get('https://graph.facebook.com/v21.0/'+PAGE,params={'fields':'name,instagram_business_account{id,username}','access_token':t},timeout=20).json()
iba=(r.get('instagram_business_account') or {})
print('5 페이지-IG :',r.get('name'),iba,'| env일치:',iba.get('id')==u)
r2=requests.get('https://graph.facebook.com/v21.0/'+u,params={'fields':'id,username,media_count','access_token':t},timeout=20)
print('6 IG조회    :',r2.status_code,r2.json() if r2.status_code==200 else r2.json().get('error',{}).get('message','')[:100])
"
```

(`KEY`·`PAGE`를 대상 계정 값으로 바꿔 실행)

**합격 기준**

```
1 type      : PAGE
2 valid     : True
3 만료      : 없음(무제한)
4 publish권한: True
5 페이지-IG : {이름} {'id': '17841...', 'username': '...'} | env일치: True
6 IG조회    : 200 {...}
```

---

## 9단계. Runtime 반영

1. 크롤·게시·친구요청·AdsPower가 **모두 유휴**인지 확인
2. 관리자 PowerShell에서 재시작

```
Restart-Service SNS_Watchdog
```

3. 다음 게시 슬롯에서 `[publish_single] 성공 | ig_media_id=...` 확인

---

## 계정별 체크리스트 (수십 개 진행 시 복사해서 사용)

```
계정명:                    account_code: IDN-0000__   credential_key: ____
[ ] 1. IG 프로페셔널 전환 확인
[ ] 2. 페이지 ↔ IG 연결 (계정 센터 아님!)
[ ] 3. 실제 Page ID 확보:  ____________________
[ ] 4. Explorer: graph.facebook.com + 권한 7개 + 사용자 토큰 생성
[ ] 5. 토큰 디버거에서 "액세스 토큰 연장" 클릭 → 장기 사용자 토큰
[ ] 6. {PageID}?fields=access_token → 무제한 페이지 토큰 (따옴표 안쪽만 복사)
[ ] 7-1. .env 2줄 등록
[ ] 7-2. Airtable Account_Registry 등록 (api_provider=facebook_login)
[ ] 8. 검증 6항목 전부 통과
[ ] 9. 재시작 후 실게시 1건 성공 확인
```

---

## 자주 겪는 오류 (260925 실작업 기록)

| 증상 | 원인 | 해결 |
|---|---|---|
| `Invalid platform app` | Explorer 도메인이 `graph.instagram.com` | `graph.facebook.com`으로 변경(4단계) |
| `instagram_business_account: (없음)` | 계정 센터만 연결, 페이지↔IG 미연결 | 2단계 수행 |
| `Unsupported get request` (Page 조회) | `profile.php?id=` 숫자를 Page ID로 사용 | `me/accounts`로 실제 ID 확인(3단계) |
| `type: USER` | 페이지 토큰이 아님 | 6단계 재수행 |
| `만료`에 날짜가 찍힘 | 5단계(연장) 누락 | 5단계부터 재수행 |
| `Malformed access token` | 토큰 잘림 또는 JSON 찌꺼기 | 6단계 복사 주의사항 참조 |
| `길이=0` | 붙여넣기 실패 | `.env` 재저장 후 8단계 재검증 |
| `code 190 Session has expired` | 구 IGAA 토큰 사용 중 | 이 문서 방식으로 전환 |

---

## 부록 A. 구 방식 (`instagram_login` / IGAA) — **폐기, 신규 사용 금지**

기존 매뉴얼의 Instagram API 직접 발급 경로(앱 → Instagram 테스터 등록 → 토큰 생성)는 **60일 만료 토큰만 발급**되며, 다음 제약이 있다.

- 60일마다 전 계정 수동 재발급 필요 → 다계정 확장 시 운영 불가
- `comment_auto_reply`의 **Private Reply 미지원**(코드상 `instagram_login`이면 스킵)
- 만료 시 무인 복구 불가 — 슬롯 전량 실패

**이미 `instagram_login`으로 등록된 계정의 전환 절차**: 이 문서 1~8단계를 그대로 수행한 뒤, Airtable `api_provider`를 `instagram_login` → `facebook_login`으로 변경하고 재시작한다. `ig_user_id`는 대개 동일하므로 변경 불필요(반드시 8단계 5번으로 일치 확인).

> 참고: 구 방식은 App Review·비즈니스 인증이 불필요하다는 장점이 있었으나, 본인 소유 계정 대상이면 `facebook_login`도 Standard Access로 동작한다(260925 aijomoojin 실증).

## 부록 B. 보안 규칙

- 앱 시크릿·액세스 토큰은 **URL 히스토리·로그·채팅·스크린샷에 노출 금지**
- `.env`는 `.gitignore` 대상 — **절대 커밋하지 않는다**
- 토큰 값을 AI 어시스턴트에게 전달하지 않는다(검증은 길이·타입·만료만 확인하면 충분)
- 토큰이 노출됐다면 즉시 해당 페이지 토큰 무효화 후 5~7단계 재수행

## 부록 C. 관련 기록

- `docs/ERROR_DATABASE.md` — ERR-077/ERR-079(260725 토큰 노출·단기만료), 260925 IGAA 만료
- `docs/CURRENT_RUNTIME_CONTEXT.md` — 계정별 provider 현황
- `modules/common/credential_resolver.py` — `credential_key` → `.env` 변수 매핑 규칙
- `launcher/main.py` `PROVIDER_CONFIG` — provider별 Graph API 호스트
