# progress-015: 눈누 출처 URL 오염 원인 규명 (2026-07-28)

## 맥락

이슈 #148 제보: "효남 늘 화이팅" 폰트의 출처가 눈누 인스타그램으로 연결된다. 조사 결과 단일 폰트 문제가 아니라 **Tier B 1,110종 중 172종(15.5%)** 이 동일하게 오염된 구조적 결함이었다.

## 구현 요약

수정 파일: `apps/pipeline/src/fontagit_pipeline/noonnu_seed.py`, `apps/pipeline/tests/test_noonnu_seed.py` (PR #149)

### 근본 원인

`_extract_font_data`가 페이지 **전체**의 `<a href>`를 순회하며 `[".kr", ".com", "behance", "instagram", "github", "dribbble"]` 중 하나라도 포함하는 **첫 링크를 잡고 break**했다. 본문/푸터 구분 없음.

font_page/600 판정 추적 (재현 완료):
```
  -    https://clova.ai/handwriting/list.html      진짜 제작사, .ai라 화이트리스트 미통과
  -    https://forms.gle/...                        눈누 문의폼
  -    https://maily.so/noonnu                      눈누 뉴스레터
MATCH  https://www.instagram.com/noonnu_official/   잘못 선택
MATCH  https://www.facebook.com/projectnoonnu/
```

DOM 조상 실측으로 본문/푸터 분리 확인:
- 본문(clova.ai): `div.noon-page-content` 하위
- 푸터(SNS/뉴스레터/문의폼): `div.bg-gray-noon` 하위 (형제 노드, 포함 관계 아님)

제작사 **이름**은 JSON-LD `creator.name`에서 "네이버"로 정확히 추출되고 있었다. URL만 틀렸다. JSON-LD의 `url` 필드는 눈누 자기 페이지라 대안이 못 된다.

### 수정 4종

1. `_find_content_container()` 신설 — 선택자 우선순위 `div.noon-page-content` > `[class*="noon-page-content"]` > `main` > `article` > `None`. **페이지 전체 폴백 없음(fail-closed)**. 못 찾으면 `official_url=None` + 경고 로그. 반환값이 `official_url`과 `license_source_url` 양쪽에 쓰이므로 틀린 값보다 빈 값이 안전
2. `_NOONNU_OWN_LINK_BLOCKLIST` 신설 — `noonnu.cc`, `instagram.com/noonnu_official`, `facebook.com/projectnoonnu`, `maily.so/noonnu`, `forms.gle`
3. TLD 화이트리스트 삭제 — `.ai`를 놓친 직접 원인. 대응하면 `.io`, `.design`이 계속 나온다. 스킴 검사 + 에셋 확장자 제외만 유지
4. 회귀 테스트 6건

## 시도와 실패

**웹 검색 도구 실패**: `~/.claude/settings.json`의 `"effortLevel": "xhigh"`가 원인. 현재 모델에서 thinking 비활성 상태로 xhigh를 쓰면 API가 거부한다(`output_config.effort 'xhigh' is not supported when thinking is disabled`). `/effort`로 high로 낮추자 즉시 정상 작동. 설정에 `alwaysThinkingEnabled: true`가 있는데도 thinking이 꺼져 있던 것은 알려진 회귀 버그로 보고돼 있다.

## 결정 근거와 기각된 대안

**fail-closed 폴백 설계**: 컨테이너를 못 찾을 때 페이지 전체로 폴백하면 현재 버그가 그대로 되살아난다. 기각.

**TLD 화이트리스트에 `.ai` 추가**: 땜질. 근본은 "주소 문자열로 제작사를 판별한다"는 가정 자체가 틀린 것. 기각하고 목록 제거를 택했다.

**차단 목록의 실질 역할**: 리뷰에서 본문 영역 안 링크 29개를 전수 확인한 결과 눈누 마켓/관련 폰트 추천 링크가 다수였다. **차단 목록 없이 범위 한정만 했다면 `noonnu.cc/market/fonts/...`가 뽑혔을 것**. 2차 방어가 아니라 필수 방어였다.

## 리뷰에서 잡힌 것

**HIGH(실증 재현)**: 차단 목록 비교에만 소문자 정규화가 빠져 `https://INSTAGRAM.COM/noonnu_official`이 그대로 채택됐다. 바로 아래 에셋 검사는 `href.lower()`를 쓰고 있어 내부 일관성도 깨져 있었다. 커밋 c042672로 수정.

**LOW**: 에셋 확장자 검사가 `endswith`라 `.png?v=1`을 못 걸렀다. `urlsplit().path` 기반으로 수정.

**리뷰어 대조 실증**: 수정 전 코드를 별도로 떠서 신규 회귀 테스트 입력을 넣으니 인스타그램이 나왔고, 수정 후에는 `clova.ai`가 나왔다. 테스트 통과가 우연이 아님을 증명.

## 재현-검증 명령어

```bash
cd apps/pipeline
uv run pytest tests/test_noonnu_seed.py -v   # 16 passed
uv run python -c "
from fontagit_pipeline.noonnu_seed import _extract_font_data
print(_extract_font_data(open('/tmp/noonnu600.html').read(), 'https://noonnu.cc/font_page/600'))
"
# -> ('효남 늘 화이팅', None, '네이버', 'https://clova.ai/handwriting/list.html')
```

## 미해결 (이슈로 이관)

- **#150**: 172종 데이터 정정 + 나머지 938종 오염 검증. 938종은 "우연히 본문 링크가 먼저 매칭"됐을 뿐일 수 있다 — font_page/600에서 제작사 링크가 선택된 것도 앞선 추천 링크들이 상대경로여서 자동으로 걸러진 덕분이었다
- ⚠️ **다중 링크 선택 정책**: 본문에 외부 링크가 여럿일 때 "첫 링크 채택"의 근거가 표본 1건뿐. 대안 후보 — clova.ai의 앵커 텍스트가 "다운로드 페이지로 이동"이었으므로 앵커 텍스트 매칭, 또는 제작사명과 도메인 매칭
- ⚠️ **`main`/`article` 폴백 미검증**: 일부 사이트는 `main` 안에 푸터를 넣는다. 그런 구조가 있으면 그 폴백이 버그 재현 경로가 된다. font_page/600에서는 `main` 0개, `article` 1개(무관한 위젯)로 확인됐으나 표본 1건
