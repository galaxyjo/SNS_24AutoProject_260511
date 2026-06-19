import pathlib

ctx = pathlib.Path('docs/CURRENT_RUNTIME_CONTEXT.md')
content = ctx.read_text(encoding='utf-8')
append = '''
## [260619_세션7_실운영확인] — 2026-06-19 KST

### 완료 작업
1. launcher 재시작 → dome_crawl + dome_export 자동 등록 확인
2. D002 건강식품 Hold 등록 (recuRdoKY0KDiV7Ci)
3. 24시간 누적 확인:
   - Source_Items 21건 (EXPORTED=4 / NEW=17)
   - Instagram_Posts 도매꾹 출처 3건
   - dome_crawl 60분 / dome_export 10분 자동 실행 확인

### Known Facts
- dome_crawl: 60분 interval 실운영 중 (D001 Active)
- dome_export: 10분 interval 실운영 중
- D002 Hold (건강식품) — 다음 세션 Active 전환 검토
- Source_Items 누적 중 (10건/회)

### P0 Backlog (다음 세션)
1. D002 건강식품 Active 전환 → Runtime Proof
2. source_item_id 기준 export_to_instagram_posts target_id 확장
3. Instagram_Posts 도매꾹 출처 게시물 품질 확인
'''
ctx.write_bytes((content + append).encode('utf-8'))
print('RUNTIME_CONTEXT:', 'BOM_FOUND' if ctx.read_bytes()[:3] == b'\xef\xbb\xbf' else 'NO_BOM')

journal = pathlib.Path('porting_logs/MERGE_JOURNAL.md')
jcontent = journal.read_text(encoding='utf-8')
jappend = '''
---

## [260619_세션7_실운영확인] 2026-06-19 KST

| 항목 | 내용 |
|------|------|
| launcher 재시작 | dome_crawl + dome_export 자동 등록 확인 |
| D002 | 건강식품 Hold 등록 완료 |
| Source_Items | 21건 누적 / EXPORTED=4 |
| Instagram_Posts | 도매꾹 출처 3건 |
| 다음 세션 | D002 Active 전환 + 품질 확인 |
'''
journal.write_bytes((jcontent + jappend).encode('utf-8'))
print('MERGE_JOURNAL:', 'BOM_FOUND' if journal.read_bytes()[:3] == b'\xef\xbb\xbf' else 'NO_BOM')
print('완료')
