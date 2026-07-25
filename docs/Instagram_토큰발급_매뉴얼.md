# Instagram Graph API 토큰 발급 매뉴얼 (Standard Access, 비즈니스 인증 불필요)

**목적**: Meta 앱을 통해 특정 Instagram 계정(본인 소유/관리)의 `ig_user_id` + `access_token`을 발급받아 Airtable 등 외부 저장소에 저장.

**전제 조건**
- Meta 개발자 계정(관리자) 보유
- 발급 대상 Instagram 계정 로그인 정보 보유
- Airtable 연동(PAT)은 이미 완료된 상태 — 이 매뉴얼과 무관

---

## 1단계. Meta 앱 생성

1. `developers.facebook.com/apps/creation/` 접속.
2. **앱 상세 정보**: 앱 이름 입력, 연락처 이메일 확인 → 다음.
3. **이용 사례**: "모두" 필터 선택 → **Instagram API 설정** (또는 "Instagram으로 비즈니스 자산 관리") 선택 → 다음.
4. **비즈니스**: **"아직 비즈니스 포트폴리오를 연결하고 싶지 않음"** 선택 → 다음.
   - 비즈니스 포트폴리오 연결은 필수 아님. 인증 절차를 피하려면 이 옵션 선택.
5. **요구 사항 / 개요**: 기본값으로 진행 → 앱 만들기 완료.

## 2단계. Instagram 테스터 역할 등록

Instagram 계정으로 인증을 시도하기 전, 반드시 먼저 해당 계정을 앱의 테스터로 등록해야 함.

1. 앱 대시보드 → **앱 역할 → 역할** 메뉴 이동.
   - URL 패턴: `developers.facebook.com/apps/{app-id}/roles/roles/`
2. **"사람 추가"** 클릭.
3. **"이 앱에 대한 추가 역할"** 섹션에서 **"Instagram 테스터"** 선택 (상단 관리자/개발자/테스터 등 기본 역할과는 별개 항목).
4. 검색창에 대상 Instagram 계정과 연결된 Facebook 계정 이름 입력 → 선택 → **"추가"**.
5. 목록에 해당 계정이 **"대기 중(Pending)"** 상태로 표시됨 — 정상. 다음 단계 필요.

## 3단계. 초대 수락 (Instagram 계정 측)

1. **초대 대상 Instagram 계정으로 로그인**한 브라우저에서 접속:
   ```
   https://www.instagram.com/accounts/manage_access/
   ```
2. 상단 탭에서 **"테스터 초대"** 클릭.
3. 해당 앱 이름 확인 → **"수락"** (또는 승인) 클릭.
4. 승인 완료 문구("~에 회원님이 승인함 [날짜]") 확인.

## 4단계. Meta 개발자 콘솔로 복귀 → 역할 상태 재확인

1. 앱 대시보드 → **역할** 페이지 새로고침.
2. 대상 계정 옆 "대기 중" 표시가 사라졌는지 확인 (사라지면 활성화 완료).

## 5단계. 권한 설정 (최소 권한만)

1. **이용 사례 → 권한 및 기능** 이동.
2. 좌측 드롭다운이 **"Instagram API"**로 선택되어 있는지 확인.
3. 목적에 맞는 최소 권한만 "추가":

| 권한 | 용도 |
|---|---|
| `instagram_business_basic` | 계정 기본 정보 + 토큰 발급 필수 |
| `instagram_business_manage_messages` | 메시지 관리 필요 시에만 |
| `instagram_business_manage_comments` | 댓글 관리 필요 시에만 |
| `instagram_business_content_publish` | 게시(포스팅) 자동화 필요 시에만 |

> ⚠️ 목록에 있는 다른 권한(`ads_management`, `Human Agent` 등)은 클릭하지 않는다. Advanced Access 및 App Review/비즈니스 인증을 유발할 수 있음.

## 6단계. 액세스 토큰 생성

1. **이용 사례 → API 설정** 이동.
2. **"2. 액세스 토큰 생성"** 섹션 펼치기.
3. **"계정 추가"** 클릭 → Instagram 로그인 → 대상 계정 선택 → 권한 승인.
4. 등록 완료되면 계정명과 함께 `Instagram 계정 ID`(=`ig_user_id`)가 표시됨.
5. 같은 행의 **"토큰 생성"** 클릭 → 승인 완료 시 `access_token` 값 표시.

## 7단계. 저장

발급된 두 값을 Airtable 지정 필드에 저장:

| 필드 | 값 |
|---|---|
| `ig_user_id` | 6단계 4번에서 확인한 숫자 ID |
| `access_token` | 6단계 5번에서 표시된 토큰 문자열 |

---

## 보안 주의사항

- App Secret, access_token은 URL 히스토리·로그·공용 화면에 노출 금지.
- 단기 토큰(기본 1시간)은 장기 토큰(60일)으로 교환 권장:
  ```
  GET https://graph.facebook.com/v21.0/oauth/access_token?grant_type=fb_exchange_token&client_id={app-id}&client_secret={app-secret}&fb_exchange_token={단기토큰}
  ```
- 장기 토큰도 60일 후 만료 — 갱신 로직 별도 필요.

## 핵심 원칙 요약

- Standard Access(자기 소유 계정 대상)는 App Review·비즈니스 인증 불필요.
- 비즈니스 인증이 필요해지는 경우: 본인 소유가 아닌 제3자 계정에 서비스하거나, Advanced Access 권한을 신청할 때.
- 에러 "개발자 역할 권한 부족"의 원인은 거의 항상 **2~3단계(테스터 등록 및 수락) 누락**.
