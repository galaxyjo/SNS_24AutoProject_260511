import pathlib

ctx = pathlib.Path('docs/CURRENT_RUNTIME_CONTEXT.md')
content = ctx.read_text(encoding='utf-8')
append = '''
## [260619_세션8_D002확장] — 2026-06-19 KST

### 완료 작업
1. D002 건강식품 Active 전환
2. dome_crawl D001+D002 동시 fetch=10+10 Runtime Proof
3. _job_dome_export() target_id=None / batch_size=5 확장 (7fdd9d1)
4. exported=3 (D001+D002 혼합) Gemini caption 3건 성공

### Known Facts
- dome_crawl: D001(화장품)+D002(건강식품) Active 실운영
- dome_export: target_id=None 전체 대상 / batch_size=5
- Source_Items 누적 중
- Instagram_Posts 도매꾹 출처 증가 중

### P0 Backlog (다음 세션)
1. Instagram_Posts 도매꾹 출처 게시물 품질 육안 확인
2. 카테고리 추가 검토 (D003 등)
3. 48시간 안정성 모니터링
'''
ctx.write_bytes((content + append).encode('utf-8'))
print('RUNTIME_CONTEXT:', 'BOM_FOUND' if ctx.read_bytes()[:3] == b'\xef\xbb\xbf' else 'NO_BOM')

journal = pathlib.Path('porting_logs/MERGE_JOURNAL.md')
jcontent = journal.read_text(encoding='utf-8')
jappend = '''
---

## [260619_세션8_D002확장] 2026-06-19 KST

| 항목 | 내용 |
|------|------|
| 커밋 | 7fdd9d1 |
| D002 | 건강식품 Active 전환 + Runtime Proof |
| dome_export | target_id=None / batch_size=5 확장 |
| exported | 3건 (D001+D002 혼합) Gemini 성공 |
| 다음 세션 | 품질 확인 + 카테고리 확장 검토 |
'''
journal.write_bytes((jcontent + jappend).encode('utf-8'))
print('MERGE_JOURNAL:', 'BOM_FOUND' if journal.read_bytes()[:3] == b'\xef\xbb\xbf' else 'NO_BOM')
print('완료')
