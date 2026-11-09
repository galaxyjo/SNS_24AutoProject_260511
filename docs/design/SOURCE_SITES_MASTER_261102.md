# 원천소스 마스터 목록 (글 + 이미지) — 크롤링·자동게시용

- 저장일: 2026-11-02 (회장 제공 자료, 원문 보존)
- 용도: 23계정 자동게시의 **글 원천 / 이미지 원천** 후보 목록. 이 파일은 참조 자료이며 **Runtime에 연결돼 있지 않다**(Sourcebook 파서 `### N.N` 형식 아님, 어떤 잡도 읽지 않음).
- 상태: **미검증(UNVERIFIED)** — 아래 항목은 URL 접속, 라이선스(CC0/상업 이용), robots.txt·이용약관(크롤링 허용 여부), RSS/API 제공 여부를 아직 확인하지 않았다. 연결 전 항목별 검증이 필요하다.
- 검증 시 주의(기록용): Freepik·Canva·PNGTree·CleanPNG·Flaticon·Vecteezy·Iconfinder 등은 무료 구간에도 출처 표기·유료 혼재·재배포 제한이 있을 수 있다. 의료/피부과 항목(4·5번)은 게시 전 허위 의료 표현 Gate(B_MED)를 거쳐야 한다. 현재 Runtime의 이미지 공급은 Pexels(스톡)와 Cloudflare 생성이다.
- 중복 정책(회장 수용 261102): 계정 간 콘텐츠·이미지 중복 허용, 한 계정 내 중복 금지.

---

# CLAUDE CODE용 자동화 크롤링 및 소스 수집용 마스터 데이터베이스

이 문서는 실리콘밸리 AI 마케팅 및 자동화 전문가 관점에서 최적화된 **크롤링 및 자동 게시(Auto-Posting) 원천 소스** 목록입니다. Claude Code가 파싱하여 자동화 파이프라인(n8n, Python, Airtable 등)에 즉시 연동할 수 있도록 구조화되었습니다.

---

## 1. 전세계 고화질 무료 이미지 사이트 (50개)

크롤링 시 이미지 URL, Alt 태그, CCO/무료 라이선스 조건을 자동 수집하는 원천 소스입니다.

1. **Unsplash** - https://unsplash.com
   - #무료이미지 #고화질사진 #상업적이용 #웹디자인 #감성사진
2. **Pexels** - https://pexels.com
   - #무료동영상 #HD사진 #디자이너소재 #무료라이선스 #크리에이티브사진
3. **Pixabay** - https://pixabay.com
   - #무료일러스트 #벡터이미지 #음원소재 #무료비디오 #상업용사진
4. **Burst (by Shopify)** - https://burst.shopify.com
   - #이커머스사진 #비즈니스이미지 #트렌딩사진 #무료상업이미지 #제품촬영
5. **Freepik (Free Section)** - https://freepik.com
   - #벡터그래픽 #PSD템플릿 #아이콘 #무료리소스 #디자인자료
6. **Picjumbo** - https://picjumbo.com
   - #고해상도사진 #블로그이미지 #웹디자인소스 #무료배경사진 #상업적활용
7. **StockSnap.io** - https://stocksnap.io
   - #CC0라이선스 #매주업데이트 #고화질스톡 #자유이용 #디지털마케팅
8. **Kaboompics** - https://kaboompics.com
   - #컬러팔레트 #라이프스타일 #인테리어사진 #블로거용이미지 #감성스톡
9. **Reshot** - https://reshot.com
   - #무료SVG #독특한일러스트 #유니크사진 #아이콘팩 #디자이너자료
10. **Foodiesfeed** - https://foodiesfeed.com
    - #음식사진 #푸드블로그 #고화질요리 #레시피이미지 #푸드스타일링
11. **Rawpixel (Free)** - https://rawpixel.com/category/free-photographs
    - #빈티지아트 #퍼블릭도메인 #고화질PSD #클래식일러스트 #디자인소스
12. **Gratisography** - https://gratisography.com
    - #위트있는사진 #유쾌한이미지 #창의적스톡 #컨셉사진 #독특한디자인
13. **SplitShire** - https://splitshire.com
    - #상업용스톡 #감성비디오 #웹용사진 #디자이너전용 #무료이미지
14. **Skitterphoto** - https://skitterphoto.com
    - #퍼블릭도메인 #CC0사진 #풍경사진 #자연스톡 #자유재활용
15. **Life of Pix** - https://lifeofpix.com
    - #고화질풍경 #도시사진 #포토그래퍼자료 #주간추천사진 #무료비디오
16. **Picography** - https://picography.co
    - #고해상도스톡 #도시라이프 #인증샷소재 #상업적자유 #라이프스타일
17. **ISO Republic** - https://isorepublic.com
    - #무료스톡비디오 #고화질이미지 #마케팅자료 #비즈니스스톡 #크리에이티브
18. **New Old Stock** - https://nos.tines.dev
    - #빈티지사진 #역사적기록 #클래식흑백 #퍼블릭도메인 #레트로이미지
19. **ShotStash** - https://shotstash.com
    - #크리에이티브스톡 #배경화면 #웹디자인자료 #고화질텍스처 #무료배포
20. **Styled Stock** - https://styledstock.co
    - #페미닌스타일 #여성라이프스타일 #데스크테리어 #블로그스톡 #유니크디자인
21. **Jay Mantri** - https://jaymantri.com
    - #자연풍경 #도심스냅 #시네마틱사진 #무료스톡 #크리에이티브사진
22. **Magdeleine** - https://magdeleine.co
    - #감성스톡 #색상별검색 #어두운톤사진 #자연스냅 #디자이너자료
23. **StockVault** - https://stockvault.net
    - #그래픽배경 #텍스처패턴 #3D렌더링 #디자인자료 #무료스톡
24. **FreeImages** - https://freeimages.com
    - #카테고리별사진 #대용량스톡 #비즈니스배경 #일러스트자료 #무료다운로드
25. **Vecteezy (Free Filter)** - https://vecteezy.com
    - #벡터아이콘 #일러스트소스 #SVG다운로드 #무료그래픽 #디자인소스
26. **CleanPNG** - https://cleanpng.com
    - #투명배경PNG #배경누끼 #무료PNG #디자인합성 #아이콘소스
27. **PNGTree (Free)** - https://pngtree.com
    - #PNG이미지 #일러스트템플릿 #배경소재 #텍스트효과 #무료그래픽
28. **Iconfinder (Free Filter)** - https://iconfinder.com
    - #무료아이콘 #UI디자인아이콘 #SVG벡터 #앱디자인 #웹아이콘
29. **Flaticon** - https://flaticon.com
    - #픽토그램 #벡터아이콘 #UIUX자료 #무료아이콘팩 #디자이너필수
30. **Font Awesome Icons** - https://fontawesome.com
    - #웹아이콘 #폰트아이콘 #개발자자료 #무료SVG #UI디자인
31. **Public Domain Vectors** - https://publicdomainvectors.org
    - #CC0벡터 #퍼블릭도메인 #무료SVG #클립아트 #그래픽디자인
32. **Canva Free Media** - https://canva.com
    - #카드뉴스소재 #SNS디자인 #무료스톡사진 #템플릿소재 #디자인툴
33. **DesignersPics** - https://designerspics.com
    - #고해상도스톡 #개념사진 #상업적이용 #비즈니스사진 #무료배포
34. **BucketListly Photos** - https://photos.bucketlistly.com
    - #여행사진 #세계여행스냅 #자연풍경 #문화사진 #여행블로그소재
35. **Good Stock Photos** - https://goodstock.photos
    - #데일리사진 #실생활스냅 #자연스러운이미지 #상업용스톡 #무료소스
36. **FoodieFactor** - https://foodiefactor.com
    - #음식스톡 #음료사진 #카페디저트 #음식블로그 #고화질푸드
37. **Startup Stock Photos** - https://startupstockphotos.com
    - #스타트업라이프 #오피스스냅 #개발자사진 #맥북작업 #비즈니스이미지
38. **MMT Stock** - https://mmtstock.com
    - #자연텍스처 #도시풍경 #작업공간사진 #고화질스톡 #디자이너추천
39. **Barnimages** - https://barnimages.com
    - #비스톡사진 #독특한감성 #고화질스냅 #라이프스타일 #웹디자인자료
40. **Foter** - https://foter.com
    - #인테리어사진 #가구스톡 #홈스타일링 #대용량사진 #무료이미지
41. **Free Nature Stock** - https://freenaturestock.com
    - #자연풍경사진 #밤하늘사진 #자연스톡 #매일업데이트 #CC0라이선스
42. **Creative Commons Photos (Openverse)** - https://openverse.org
    - #크리에이티브커먼즈 #공공재이미지 #대용량검색 #학술용자료 #무료스톡
43. **Wikimedia Commons** - https://commons.wikimedia.org
    - #역사적사진 #지적재산공유 #학술이미지 #퍼블릭도메인 #글로벌소스
44. **Picspree** - https://picspree.com
    - #고해상도다운로드 #상업용무료 #카테고리별사진 #웹마케팅자료 #스톡이미지
45. **Realistic Shots** - https://realisticshots.com
    - #생동감있는사진 #일상스냅 #자연스러운컷 #매주업데이트 #무료다운로드
46. **Morguefile** - https://morguefile.com
    - #레퍼런스사진 #디자이너참고자료 #자유편집 #오래된스톡 #무료이미지
47. **Skitterphoto CC0** - https://skitterphoto.com/photos
    - #고화질CC0 #무료상업이용 #포토그래퍼커뮤니티 #풍경스냅 #자유가공
48. **Coverr** - https://coverr.co
    - #웹배경비디오 #HD동영상 #무료동영상스톡 #마케팅비디오 #시네마틱
49. **Mixkit** - https://mixkit.co
    - #무료비디오클립 #음악트랙 #효과음 #영상템플릿 #디지털마케팅
50. **Vidsplay** - https://vidsplay.com
    - #무료동영상소재 #웹페이지배경 #HD비디오 #매주업데이트 #크롤링소스

---

## 2. 미국 & 중국 AI 최신 소식 사이트 (10개)

미국과 중국의 테크 에이전시, 연구소 및 정책 트렌드를 트래킹하는 매체입니다.

1. **TechCrunch AI** - https://techcrunch.com/category/artificial-intelligence
   - #미국AI스타트업 #AI투자동향 #빅테크소식 #테크뉴스 #실리콘밸리트렌드
2. **MIT Technology Review AI** - https://technologyreview.com/topic/artificial-intelligence
   - #AI윤리정책 #딥테크분석 #차세대AI기술 #학술트렌드 #미국연구소소식
3. **VentureBeat AI (AI Beat)** - https://venturebeat.com/category/ai
   - #엔터프라이즈AI #생성형AI트렌드 #AI비즈니스모델 #미국테크뉴스 #LLM동향
4. **China AI Report (South China Morning Post)** - https://scmp.com/tech/enterprises
   - #중국AI트렌드 #바이두알리바바 #중국테크 규제 #중국LLM #아시아테크
5. **Jiqizhixin (시계지능 / 机器之心)** - https://jiqizhixin.com
   - #중국최대AI매체 #중국AI연구소 #논문해설 #중국빅테크AI #딥러닝소식
6. **Synced (상탕/시계지능 영문)** - https://syncedreview.com
   - #중국AI글로벌소식 #글로벌AI비교 #중국AI스타트업 #연구논문분석 #글로벌트렌드
7. **The Information (AI section)** - https://theinformation.com/ai
   - #실리콘밸리비공개소식 #AI스타트업투자 #미국AI단독보도 #빅테크내부동향 #고급테크뉴스
8. **AI News (TelecomTV)** - https://artificialintelligence-news.com
   - #글로벌AI정책 #미중AI경쟁 #산업용AI #AI기술트렌드 #스마트엔터프라이즈
9. **Pandaily (China Tech)** - https://pandaily.com
   - #중국테크생태계 #중국스타트업 #중국AI서비스 #중국IT소식 #아시아빅테크
10. **The Verge - AI Section** - https://theverge.com/ai-artificial-intelligence
    - #빅테크AI뉴스 #소비자AI제품 #미국AI이슈 #생성형AI #테크트렌드

---

## 3. 실리콘밸리 전문가들이 주로 보는 AI 사이트 (10개)

현지 엔지니어, VC, AI 리서처들이 매일 모니터링하는 전문 사이트입니다.

1. **Hugging Face Daily Papers** - https://huggingface.co/papers
   - #최신AI논문 #실리콘밸리엔지니어 #오픈소스모델 #LLM트렌드 #딥러닝연구
2. **ArXiv Computer Science (AI)** - https://arxiv.org/list/cs.AI/recent
   - #AI연구논문 #세계최초기술 #실리콘밸리리서치 #학술원천소스 #기술트렌드
3. **SemiAnalysis** - https://semianalysis.com
   - #AI반도체분석 #NVIDIA엔비디아 #데이터센터인프라 #실리콘밸리분석 #AI칩트렌드
4. **The Batch (by Andrew Ng / DeepLearning.AI)** - https://deeplearning.ai/the-batch
   - #앤드류응뉴스레터 #AI산업핵심요약 #엔지니어필독 #실리콘밸리트렌드 #AI에이전트
5. **Import AI (by Jack Clark)** - https://importai.substack.com
   - #AI안전성 #AI정책동향 #실리콘밸리트렌드 #LLM안전성 #테크분석
6. **Latent Space Substack** - https://latent.space
   - #AI엔지니어링 #AI에이전트개발 #실리콘밸리현장뉴스 #LLMOps #개발자트렌드
7. **Techmeme** - https://techmeme.com
   - #실리콘밸리헤드라인 #테크뉴스집계 #AI이슈클러스터링 #실시간테크뉴스 #엔지니어필독
8. **Hacker News (Y Combinator)** - https://news.ycombinator.com
   - #실리콘밸리개발자 #YCombinator #AI스타트업토론 #오픈소스프로젝트 #실시간개발트렌드
9. **GitHub Trending (Python/C++)** - https://github.com/trending
   - #오픈소스AI코드 #신규AI레포지토리 #실리콘밸리코드트렌드 #개발자원소스 #AI라이브러리
10. **Paper with Code** - https://paperswithcode.com
    - #논문과코드연동 #AI벤치마크 #SOTA성능비교 #실리콘밸리리서치 #딥러닝소스

---

## 4. 미국 피부과 최신 뉴스 & 트렌드 사이트 (5개)

선진 피부과 치료 기술, 의료기기, 시술 트렌드 자동 수집용입니다.

1. **Dermatology Times** - https://dermatologytimes.com
   - #미국피부과뉴스 #신약승인소식 #의료기기트렌드 #피부질환치료 #미국임상트렌드
2. **Journal of the American Academy of Dermatology (JAAD)** - https://jaad.org
   - #미국피부과학회 #최신의학논문 #피부과임상연구 #선진치료기술 #의학전문소식
3. **Practical Dermatology** - https://practicaldermatology.com
   - #피부과클리닉운영 #에스테틱트렌드 #미국시술소식 #미용피부과 #피부과의사저널
4. **Aesthetics Wire / Modern Aesthetics** - https://modernaesthetics.com
   - #미국에스테틱트렌드 #안티에이징시술 #레이저치료기기 #미국쁘띠성형 #피부재생기술
5. **Skin Pharmacology and Physiology** - https://karger.com/spp
   - #피부생리학 #피부장벽연구 #코스메슈티컬 #미국피부과학 #화장품유효성분

---

## 5. 한국 피부과 & 쁘띠성형 최신 제품 트렌드 사이트 (5개)

보톡스, 필러, 실리프팅, 에너지 기반 장비(EBD) 신제품 및 임상 소식 소스입니다.

1. **메디컬투데이 (성형/피부 섹션)** - https://mdtoday.co.kr
   - #한국쁘띠성형뉴스 #보톡스신제품 #실리프팅트렌드 #피부과장비소식 #한국에스테틱
2. **청년의사 (피부/성형 에스테틱)** - https://docdocdoc.co.kr
   - #의료전문지 #한국피부과트렌드 #스킨부스터신제품 #의료기기인허가 #한국임상소식
3. **의학신문 (피부성형)** - https://bosa.co.kr
   - #한국의학뉴스 #보툴리눔톡신 #국산필러트렌드 #피부과시술정보 #제약바이오소식
4. **의사신문 (에스테틱/피부)** - https://doctorstimes.com
   - #피부과의원트렌드 #쁘띠성형신기술 #실리프팅임상 #한국에스테틱뉴스 #피부과의사신문
5. **메디컬타임즈 (피부성형 에스테틱)** - https://medicaltimes.com
   - #의료개원정보 #쁘띠성형트렌드 #피부과신기술 #한국피부과제품 #에스테틱의학

---

## 6. 한국 미공개 해외 크루즈 특가 & 리뷰 정보 사이트 (5개)

한국 시장에 덜 알려졌지만 미국/유럽 전문가들이 사용하는 자동화 크롤링 원소스입니다.

1. **Cruise Critic** - https://cruisecritic.com
   - #전세계크루즈리뷰 #선사별객실평가 #글로벌크루즈트렌드 #선상팁 #크루즈전문매체
2. **Vacations To Go** - https://vacationstogo.com
   - #90일땡처리크루즈 #해외크루즈초특가 #글로벌선사할인 #크루즈직구소식 #선실할인정보
3. **Shipmap.org** - https://shipmap.org
   - #전세계크루즈실시간위치 #항로시각화 #크루즈운항데이터 #해양트래픽 #크루즈지도
4. **Cruise Hive** - https://cruisehive.com
   - #크루즈산업뉴스 #신규크루즈선박 #선사별운항소식 #기항지 최신뉴스 #글로벌크루즈
5. **Ponant Official Magazine / News** - https://ponant.com
   - #럭셔리탐험크루즈 #북극남극크루즈 #소형프리미엄선박 #하이엔드크루즈 #유럽크루즈트렌드

---

## 7. 베트남 크루즈 (하롱베이·란하베이) 정보 사이트 (3개)

하롱베이, 란하베이, 깟바섬 전문 일일 및 숙박 크루즈 크롤링 원소스입니다.

1. **Halong Bay Cruise Trip** - https://halongbaycruisetrip.com
   - #하롱베이크루즈 #베트남럭셔리크루즈 #란하베이투어 #하롱베이2박3일 #베트남크루즈예약
2. **Indochina Sails Official** - https://indochinasails.com
   - #베트남전통크루즈 #하롱베이5성급 #목조크루즈 #인도차이나크루즈 #베트남고급투어
3. **Heritage Cruises (Lan Ha Bay)** - https://heritagecruises.com
   - #란하베이럭셔리크루즈 #베트남문화크루즈 #부티크크루즈 #베트남해양투어 #깟바섬크루즈

---

## Claude Code 연동을 위한 실행 스크립트 예시 (Python Beautiful Soup & RSS)

```python
import feedparser
import requests
from bs4 import BeautifulSoup

# 예시: RSS 및 Web Scraping 파싱 기본 구조
def fetch_tech_news(rss_url):
    feed = feedparser.parse(rss_url)
    articles = []
    for entry in feed.entries[:5]:
        articles.append({
            "title": entry.title,
            "link": entry.link,
            "published": entry.get("published", "")
        })
    return articles

# 예시: 이미지 태그 및 Alt 속성 자동 수집 (SEO 최적화용)
def extract_image_seo(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    images = []
    for img in soup.find_all('img', src=True):
        images.append({
            'src': img['src'],
            'alt': img.get('alt', '무료 이미지')
        })
    return images

```
